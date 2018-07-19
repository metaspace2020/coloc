<template>
  <div
    ref="container"
    class="container"
    :tabindex="0"
    @keydown="handleKeyDown"
    @keyup="handleKeyUp"
    @mouseenter="$refs.container.focus()"
    @mousedown="handleMouseDown"
    @contextmenu.prevent
  >
    <div class="floatingHeader">
      <div style="background-color: #CCFFCC; cursor: pointer;" :style="{fontWeight: labelFilter === 'on' ? 'bold' : 'normal'}" @click="handleFilterByLabel('on')">{{ stats.on }} on-sample</div>
      <div style="background-color: #FFCCCC; cursor: pointer;" :style="{fontWeight: labelFilter === 'off' ? 'bold' : 'normal'}" @click="handleFilterByLabel('off')">{{ stats.off }} off-sample</div>
      <div style="background-color: #FFFFCC; cursor: pointer;" :style="{fontWeight: labelFilter === 'ind' ? 'bold' : 'normal'}" @click="handleFilterByLabel('ind')">{{ stats.ind }} unknown</div>
      <div style="background-color: #EEEEEE; cursor: pointer;" :style="{fontWeight: labelFilter === 'un' ? 'bold' : 'normal'}" @click="handleFilterByLabel('un')">{{ stats.un }} unassigned</div>
      <div v-if="labelFilter" style="cursor: pointer;" @click="handleFilterByLabel(null)">Show all</div>
    </div>
    <div class="header">
      <div style="display: none;">
        <filter-panel level="imageclassifier" />
      </div>
      <ul>
        <li>Left-click or + to mark an image as <span style="background-color: #CCFFCC" >on-sample</span></li>
        <li>Right-click or - to mark an image as <span style="background-color: #FFCCCC" >off-sample</span></li>
        <li>Both mouse buttons or 0 to mark an image as <span style="background-color: #FFFFCC" >unknown</span></li>
        <li>Backspace or Delete to unmark an image</li>
        <li>You can click-and-drag or press a key and sweep your mouse across multiple images to mark them quickly</li>
      </ul>
    </div>
    <div class="list" v-loading="loading">
      <image-classifier-block
        v-for="(block, idx) in blocks"
        :key="idx"
        v-bind="block"
        :numCols="numCols"
        :annotationLabels="annotationLabels"
        :annotations="block"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      />
    </div>
    <div v-if="allAnnotations != null && allAnnotations.length === 0">
      Please select a dataset.
    </div>
  </div>
</template>
<script lang="ts">
  import Vue from 'vue';
  import { Component, Watch } from 'vue-property-decorator';
  import FilterPanel from '../../../components/FilterPanel.vue';
  import ImageClassifierBlock from './ImageClassifierBlock.vue';
  import * as config from '../../../clientConfig.json';
  import {confetti} from 'dom-confetti';
  import { chunk, cloneDeep, get, keyBy, mapValues, omit, pick, range } from 'lodash-es';
  import Prando from 'prando';
  import { AnnotationLabel, ICBlockAnnotation, ICBlockAnnotationsQuery } from './ICBlockAnnotation';
  import './importTool';

  const LABELS = ['un', 'on', 'off', 'ind'];


  const onKeys = ['+','=','CTRL', 'MOUSE0'];
  const offKeys = ['-', 'SHIFT', 'MOUSE2'];
  const indKeys = ['0']; // or both an onKey and offKey
  const undoKeys = ['Backspace','Delete'];
  const keysToPrevent = [...onKeys, ...offKeys, ...indKeys, ...undoKeys];

  const qs = (obj: Object) => '?' + Object.entries(obj)
    .map(([key, val]) => `${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
    .join('&');

  @Component({
    components: {
      ImageClassifierBlock,
      FilterPanel,
    },
    apollo: {
      allAnnotations: {
        query: ICBlockAnnotationsQuery,
        variables(this: ImageClassifierPage) {
          return this.gqlFilter;
        },
        loadingKey: 'loading',
        skip(this: ImageClassifierPage) {
          if (!this.datasetId || !this.user) {
            this.allAnnotations = [];
            return true;
          }
          return false;
        },
      },
    },
  })
  export default class ImageClassifierPage extends Vue {
    loading = 0;
    numCols = 4;
    allAnnotations?: ICBlockAnnotation[];
    keys: Record<string, boolean> = {};
    selectedAnnotation: ICBlockAnnotation | null = null;
    annotationLabels: Record<string, number> = {};
    blocks: ICBlockAnnotation[][] = [];

    created() {
      this.loadLabels();
      document.addEventListener('mouseup', this.handleMouseUp);
      // window.addEventListener('beforeunload', this.handleBeforeUnload);
    }
    mounted() {
      (this.$refs.container as any).focus();
    }
    beforeDestroy() {
      document.removeEventListener('mouseup', this.handleMouseUp);
      // window.removeEventListener('beforeunload', this.handleBeforeUnload);
    }

    get stats() {
      let on = 0, off = 0, ind = 0, un = 0;
      // Who needs efficient algorithms? This still manages to run in <1ms when there are 800 annotations!
      this.sampledAnnotations.forEach(({id}) => {
        const label = this.annotationLabels[id];
        if (label === 1) on++;
        else if (label === 2) off++;
        else if (label === 3) ind++;
        else un++;
      });

      return {on, off, ind, un}
    }
    get gqlFilter () {
      return {
        filter: this.$store.getters.gqlAnnotationFilter,
        datasetFilter: this.$store.getters.gqlDatasetFilter,
      };
    }
    get datasetId(): string  | null {
      return this.$store.getters.gqlDatasetFilter.ids;
    }
    get user(): string | null {
      return this.$route.query.user;
    }
    get max(): number {
      return Number.parseInt(this.$route.query.max) || 1000;
    }
    get labelFilter(): string | undefined {
      return this.$route.query.label;
    }
    get sampledAnnotations(): ICBlockAnnotation[] {
      if (this.allAnnotations != null && this.datasetId != null) {
        const annotations = this.allAnnotations.slice();
        // Cut down to desired size, hopefully in a relatively repeatable fashion
        const rng = new Prando(this.datasetId);
        while (annotations.length > this.max) {
          annotations.splice(rng.nextInt(0, 5000), 1);
        }
        return annotations;
      }
      return []
    }

    @Watch('sampledAnnotations')
    @Watch('labelFilter')
    updateBlocks() {
      // Apply label-based filters lazily so that the page doesn't constantly update
      const idx = this.labelFilter == null ? -1 : LABELS.indexOf(this.labelFilter);
      const labelFilter = idx === -1 ? null : idx;
      let filteredAnnotations: ICBlockAnnotation[];
      if (idx === -1) {
        filteredAnnotations = this.sampledAnnotations;
      } else if (idx === 0) {
        filteredAnnotations = this.sampledAnnotations.filter(({id}) => this.annotationLabels[id] == null);
      } else {
        filteredAnnotations = this.sampledAnnotations.filter(({id}) => this.annotationLabels[id] === idx);
      }
      this.blocks = chunk(filteredAnnotations, 12);
    }


    handleBeforeUnload(e: Event) {
      e.preventDefault();
      e.returnValue = true;
    }

    handleKeyDown(event: KeyboardEvent) {
      this.keys[event.key] = true;
      if (keysToPrevent.includes(event.key)) {
        event.preventDefault();
      }
      this.doSelection(event);
    }

    handleKeyUp(event: KeyboardEvent) {
      this.keys[event.key] = false;
      if (keysToPrevent.includes(event.key)) {
        event.preventDefault();
      }
      this.doSelection(event);
    }

    handleMouseDown(event: MouseEvent) {
      const key = `MOUSE${event.button}`;
      this.keys[key] = true;
      if (keysToPrevent.includes(key)) {
        event.preventDefault();
      }
      this.doSelection(event);
    }

    handleMouseUp(event: MouseEvent) {
      const key = `MOUSE${event.button}`;
      if (this.keys[key]) {
        this.keys[key] = false;
        if (keysToPrevent.includes(key)) {
          event.preventDefault();
        }
      }
      // this.doSelection(event);
    }

    handleMouseEnter(event: MouseEvent & { annotation: ICBlockAnnotation }) {
      this.selectedAnnotation = event.annotation;
      this.doSelection(event);
    }

    handleMouseLeave(event: MouseEvent & { annotation: ICBlockAnnotation }) {
      if (this.selectedAnnotation == event.annotation) {
        this.selectedAnnotation = null;
      }
    }

    handleFilterByLabel(label: string | null) {
      if (this.$route.query.label === label || label == null) {
        this.$router.push({
          query: omit(this.$route.query, 'label')
        })
      } else {
        this.$router.push({
          query: {
            ...this.$route.query,
            label
          }
        })
      }
    }

    fieldsForAnnotation({dataset, id, sumFormula, adduct, msmScore, fdrLevel, mz, isotopeImages}: ICBlockAnnotation) {
      return {
        datasetId: dataset.id,
        dsName: dataset.name,
        annotationId: id,
        sumFormula, adduct, msmScore, fdrLevel, mz,
        ionImageUrl: get(isotopeImages, [0, 'url']),
      }
    }

    async doSelection(event?: Event) {
      if (this.allAnnotations && this.selectedAnnotation) {
        const on = onKeys.some(key => this.keys[key]);
        const off = offKeys.some(key => this.keys[key]);
        const ind = (on && off) || indKeys.some(key => this.keys[key]);
        const undo = undoKeys.some(key => this.keys[key]);


        if (on || off || ind || undo) {
          const lastType = this.annotationLabels[this.selectedAnnotation.id];
          const type = undo ? null : ind ? 3 : on ? 1 : 2;
          if (lastType !== type) {
            Vue.set(this.annotationLabels, this.selectedAnnotation.id, type);

            if (!lastType && this.stats.un === 0 && this.allAnnotations.length > 0 && event && event.target) {
              let el = event.srcElement;
              while (el && el.parentElement && !el.classList.contains('annotation'))
                el = el.parentElement;

              confetti(el, {elementCount: 100});
            }

            try {
              await fetch(`${config.imageClassifierUrl}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                  ...this.fieldsForAnnotation(this.selectedAnnotation),
                  user: this.user,
                  source: 'UI',
                  type,

                })
              });
            } catch (err) {
              this.$alert(err, "Something went terribly wrong");
              Vue.set(this.annotationLabels, this.selectedAnnotation.id, 4);
            }
          }
        }
      }
    }

    @Watch('datasetId')
    @Watch('user')
    async loadLabels() {
      const datasetId = this.datasetId;
      const user = this.user;

      if (datasetId && user) {
        const query = qs({ datasetId, user });
        try {
          this.loading += 1;
          const response = await fetch(`${config.imageClassifierUrl}${query}`);
          const labels = await response.json() as Record<string, number>;
          // Double-check nothing has changed while loading
          if (datasetId === this.datasetId && user === this.user) {
            this.annotationLabels = labels;
          }

        } catch (err) {
          console.log(err);
          if (datasetId === this.datasetId && user === this.user) {
            this.annotationLabels = {};
            this.$alert("Could not load previous classifications")
          }
        } finally {
          this.loading -= 1;
        }
      } else {
        this.annotationLabels = {};
      }
    }
  }
</script>
<style scoped lang="scss">
  .container {

  }
  .floatingHeader {
    position: fixed;
    width: 100%;
    background-color: white;
    top: 0;
    font-size: 20px;
    display: flex;
    flex-direction: row;
    justify-content: center;
    z-index:100;
    >* {
      width: 200px;
      text-align: center;
    }
  }
</style>
