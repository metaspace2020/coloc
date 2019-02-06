<template>
  <div
    ref="container"
    class="container"
    v-loading="loading"
  >
    <div class="floatingHeaderContainer" v-if="!loading && numPixels > 0">
      <div class="floatingHeader">
        <div style="background-color: #CCFFCC; cursor: pointer;" @click="goBack()">&lsaquo; Save & Go Back</div>
        <div v-if="currentSetIdx < setIds.length">
          {{ currentSetIdx+1 }} out of {{ setIds.length }} (id: {{setIds[currentSetIdx]}}, mol: {{ currentSet && (currentSet.baseSf + currentSet.baseAdduct) }})
        </div>
        <div v-else>FINISHED</div>
        <div v-if="currentSetIdx < setIds.length">
          <el-checkbox v-model="currentSetIsIncomplete" label="Incomplete" />
        </div>
        <div style="background-color: #FFCCCC; cursor: pointer;" @click="goForward()">Save & Continue &rsaquo;</div>
      </div>
    </div>
    <div class="header">
      <div v-show="showfilters">
        <filter-panel level="imageclassifier" />
      </div>
    </div>
    <div class="blockContainer">
      <image-classifier-block
        v-if="!loading && numPixels > 0 && annotations.length >= setIds.length && annotations.length >= 12"
        v-for="(setId, setIdx) in setIds"
        :key="setId"
        :thisSet="getSet(setIdx)"
        :visible="setIdx === currentSetIdx"
        :preload="Math.abs(setIdx - currentSetIdx) < 2"
        :selectedIdx.bind="selectedIdx"
        :style="getBlockStyle(setIdx)"
        :base1="base1">
        <ul slot="intro">
          <li>
            <!--Drag and drop images {{base1 ? '1-10' : '0-9'}} in order from most to least colocalized to the reference image.-->
            Drag images from the <b>Unranked</b> area into rankings <b>{{base1 ? '1-10' : '0-9'}}</b> in order from most to least colocalized.
          </li>
          <li>
            If multiple images have the same degree of colocalization, it's possible to put them at the same ranking.
          </li>
          <!--
          <li>
            Alternatively, use the number keys to move them e.g. press 5 then 2 to move image 5 into the 2nd position
            <el-button type="text" @click="base1 = !base1">
              {{base1 ? 'Use numbers 0-9 instead (better for keypads)' : 'Use numbers 1-10 instead (better for laptops)'}}
            </el-button>
          </li>
          -->
          <li>Click "Save & Continue" after finishing every set, or use the left & right arrow keys to move back and forward.</li>
          <li>If you aren't able to finish ranking, or if some images can't be ranked, make sure that the "Incomplete" checkbox is checked when you move to the next set.</li>
          <li v-if="!filterCompleted">Once finished, you can <a href="#" @click.prevent="toggleFilterCompleted">hide completed sets</a> to review any remaining incomplete sets.</li>
          <li v-else><a href="#" @click.prevent="toggleFilterCompleted">Show completed sets</a>.</li>
        </ul>
      </image-classifier-block>
      <div v-if="!loading && (annotations.length < setIds.length || annotations.length < 12)">
        No dataset found, or not enough annotations matching filters
      </div>
      <div v-if="!loading && currentSetIdx === setIds.length">
        <div v-if="filterCompleted && setIds.length === 0">
          <li><a href="#" @click.prevent="toggleFilterCompleted">Show completed sets</a></li>
        </div>
        <div v-else>
          FINISHED!
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  import Vue from 'vue';
  import { Component, Watch } from 'vue-property-decorator';
  import ImageClassifierBlock from './ImageClassifierBlock.vue';
  import * as config from '../../../clientConfig-coloc.json';
  import {castArray, cloneDeep, debounce, flatMap, forEach, fromPairs, isEqual, keyBy, range} from 'lodash-es';
  import {quantile} from 'simple-statistics';
  import Prando from 'prando';
  import { ColocSet, ICBlockAnnotation, ICBlockAnnotationsQuery } from './ICBlockAnnotation';
  import './importTool';
  import {FilterPanel} from '../../Filters';
  import draggable from 'vuedraggable';
  import ImageLoader from '../../../components/PlainImageLoader.vue';


  const qs = (obj: Object) => '?' + Object.entries(obj)
    .map(([key, val]) => `${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
    .join('&');

  @Component<ImageClassifierPage>({
    components: {
      ImageClassifierBlock,
      ImageLoader,
      FilterPanel,
      draggable
    },
    apollo: {
      allAnnotations: {
        query: ICBlockAnnotationsQuery,
        variables(this) {
          return this.gqlFilter;
        },
        loadingKey: 'loading',
        skip(this) {
          if (!this.datasetId || !this.user) {
            this.allAnnotations = [];
            return true;
          }
          return false;
        }
      },
    },
  })
  export default class ImageClassifierPage extends Vue {
    loading = 0;
    allAnnotations: ICBlockAnnotation[] = [];
    serverSets: Record<string, ColocSet | null> = {};
    clientSets: Record<string, ColocSet | null> = {};
    selectedIdx: number | null = null;
    numPixels = 0;
    base1 = true;
    dirty = false;
    filterCompleted = false;
    lastCompletedSetIds: number[] = [];

    created() {
      const ignoredPromise = this.loadSets();
      this.updateFilters();
      // Debounce because HMR often causes many copies of the same listener
      this.handleKeyPress = debounce(this.handleKeyPress, 10);
      this.handleKeyDown = debounce(this.handleKeyDown, 10);
    }
    mounted() {
      document.addEventListener('keypress', this.handleKeyPress, true);
      document.addEventListener('keydown', this.handleKeyDown, true);
    }
    beforeDestroy() {
      document.removeEventListener('keypress', this.handleKeyPress);
      document.removeEventListener('keydown', this.handleKeyDown);
    }

    get currentSetIdx() {
      return parseInt(this.$route.query.idx) | 0;
    }
    set currentSetIdx(value: number) {
      this.$router.replace({
        query: {
          ...this.$route.query,
          idx: String(value),
        }
      })
    }
    get gqlFilter () {
      return {
        filter: this.$store.getters.gqlAnnotationFilter,
        datasetFilter: this.$store.getters.gqlDatasetFilter,
      };
    }
    get storeFilters() {
      return this.$store.getters.filter;
    }

    filters: any = {};
    @Watch('storeFilters')
    updateFilters() {
      // Vue should be doing a better job on watches. Every route change is causing every computed that
      // accesses a filter to recompute, which is slooooow. This even happens when the filter
      // is wrapped in its own computed.
      if (!isEqual(this.$store.getters.filter, this.filters)) {
        console.log('updating filters');
        forEach(this.$store.getters.filter, (v, k) => {
          Vue.set(this.filters, k, v);
        });
      } else {
        console.log('not updating filters')
      }
    }
    get datasetId(): string | null { return castArray(this.filters.datasetIds)[0]; }
    get user(): string | null { return this.filters.user; }
    get intThreshold() { return parseFloat(this.filters.intThreshold) || 0; }
    get showfilters(): boolean {
      return !!this.$route.query.showfilters;
    }
    get annotations(): ICBlockAnnotation[] {
      if (this.intThreshold !== 0 && this.numPixels === 0) {
        return [];
      } else if (this.allAnnotations == null) {
        return [];
      } else {
        // Randomize
        const rng = new Prando(this.datasetId || 'seed');
        let result: ICBlockAnnotation[] = [];
        const annotations = this.allAnnotations.slice();
        while (annotations.length > 0) {
          result.push(annotations.splice(rng.nextInt(0, annotations.length - 1), 1)[0])
        }

        // Filter
        if (this.intThreshold !== 0) {
          const ints = this.allAnnotations.map(this.getAnnotationAvgInt);
          console.log('Image average intensity deciles:', fromPairs(range(0, 11).map(q => [q / 10, quantile(ints, q / 10)])));

          result = result.filter((ann, idx) => ints[idx] > this.intThreshold);
        }

        return result;
      }
    }
    get unfilteredsetIds(): number[] {
      if (this.$route.query.sets) {
        return flatMap(this.$route.query.sets.split(','), setId => {
          if (setId.includes('-')) {
            const [lo, hi] = setId.split('-');
            return range(parseInt(lo, 10) | 0, (parseInt(hi, 10) | 0) + 1);
          } else {
            return [parseInt(setId, 10) | 0];
          }
        })
      } else {
        return range(10);
      }
    }
    get setIds(): number[] {
      if (this.filterCompleted) {
        return this.unfilteredsetIds
          .filter(id => id < this.annotations.length)
          .filter(id => !this.lastCompletedSetIds.includes(id));
      } else {
        return this.unfilteredsetIds.filter(id => id < this.annotations.length);
      }
    }
    get currentSet() {
      return this.getSet(this.currentSetIdx);
    }
    get currentSetIsIncomplete() {
      if (this.currentSet) {
        return this.isSetIncomplete(this.currentSet);
      } else {
        return true;
      }
    }
    set currentSetIsIncomplete(value: boolean) {
      if (this.currentSet) {
        this.currentSet.isIncomplete = value;
      }
    }
    getSet(setIdx: number) {
      return this.getSetById(this.setIds[setIdx], setIdx);
    }
    getSetById(setId: number, setIdx: number): ColocSet | null {
      const annotation = this.annotations[setId];
      if (annotation != null) {
        const annotationId = annotation.id;
        if (this.clientSets[annotationId] == null) {
          if (this.serverSets[annotationId] != null) {
            Vue.set(this.clientSets, annotationId, cloneDeep(this.serverSets[annotationId]));
          } else {
            Vue.set(this.clientSets, annotationId, this.makeSet(annotation, setIdx));
          }
        }
        return this.clientSets[annotationId];
      } else {
        return null;
      }
    }

    isSetIncomplete(set: ColocSet) {
      return set.isIncomplete != null
        ? !!set.isIncomplete
        : !set.otherAnnotations.every(a => a.rank != null);
    }

    getAnnotationAvgInt(ann: ICBlockAnnotation) {
      const iso = ann.isotopeImages[0];
      return iso.totalIntensity / iso.maxIntensity / this.numPixels;
    }

    handleKeyDown(event: KeyboardEvent) {
      if ((event.target as HTMLElement).closest('input') == null) {
        if (event.key === 'ArrowLeft') {
          this.goBack();
          event.preventDefault();
        } else if (event.key === 'ArrowRight') {
          this.goForward();
          event.preventDefault();
        }
      }
    }

    handleKeyPress(event: KeyboardEvent) {
      if ((event.target as HTMLElement).closest('input') == null) {
        const idx = (this.base1 ? '1234567890' : '0123456789').indexOf(event.key);
        if (idx !== -1) {
          if (this.selectedIdx == null) {
            this.selectedIdx = idx;
            event.preventDefault();
          } else if (this.currentSet != null && this.currentSet.otherAnnotations.length === 10) {
            console.log('swapping', this.selectedIdx, idx, this.currentSet);
            const ann = this.currentSet.otherAnnotations.splice(this.selectedIdx, 1)[0];
            this.currentSet.otherAnnotations.splice(idx, 0, ann);
            this.selectedIdx = null;
            event.preventDefault();
          }
        }
      }
    }

    toggleFilterCompleted() {
      const ignoredPromise = this.save();
      if (!this.filterCompleted) {
        this.lastCompletedSetIds = this.unfilteredsetIds
          .filter(id => id < this.annotations.length)
          .filter((id, idx) => !this.isSetIncomplete(this.getSetById(id, idx)!));
      }
      this.filterCompleted = !this.filterCompleted;
      this.currentSetIdx = 0;
    }

    goBack() {
      const ignoredPromise = this.save();
      if (this.currentSetIdx > 0) {
        this.currentSetIdx--;
      }
      this.selectedIdx = null;
    }

    goForward() {
      const ignoredPromise = this.save();
      if (this.currentSetIdx < this.setIds.length) {
        this.currentSetIdx++;
      }
      this.selectedIdx = null;
    }

    async save() {
      const setIdx = this.currentSetIdx;
      if (setIdx === this.setIds.length) return;
      const currentSet = this.currentSet!;
      const annotationId = currentSet.baseAnnotationId;

      if (!isEqual(currentSet, this.serverSets[annotationId])
        && (currentSet.otherAnnotations.some(a => a.rank != null) || currentSet.isIncomplete != null)) {
        console.log('saving', annotationId);
        try {
          const response = await fetch(`${config.manualSortUrl}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentSet)
          });
          if (response.status >= 300) {
            throw new Error(`Unexpected response from server: ${response.status} ${response.statusText}`)
          }

          Vue.set(this.serverSets, annotationId, currentSet);
          this.clientSets[annotationId] = null;
        } catch (err) {
          console.error(err);
          const ignoredPromise = this.$alert(err, `Something went wrong while saving set ${setIdx+1}. Please go back to it and click save again`);
        }
      }
    }

    @Watch('allAnnotations')
    async countPixels() {
      if (this.allAnnotations.length > 0) {
        try {
          this.loading++;
          const img = new Image();
          let checkerId;
          await new Promise((resolve, reject) => {
            const url = (config.imageStorage || '') + this.allAnnotations[0].isotopeImages[0].url;
            console.log('getting', url);
            img.onload = resolve;
            img.onerror = reject;
            img.crossOrigin = "Anonymous";
            img.src = url;

            let i = 0;
            checkerId = setInterval(() => {
              if (img.naturalHeight > 0 && img.naturalWidth > 0) {
                resolve();
              } else if (i++ > 1000) {
                reject();
              }
            }, 10);
          });
          console.log('got it')
          this.numPixels = img.naturalHeight * img.naturalWidth;
        } catch (err) {
          console.error(err);
          const ignoredPromise = this.$alert('Could not load ion image, please refresh the page and try again');
        } finally {
          this.loading--;
        }
      }
    }

    @Watch('datasetId')
    @Watch('user')
    async loadSets() {
      const datasetId = this.datasetId;
      const user = this.user;

      if (datasetId && user) {
        const query = qs({ datasetId, user });
        try {
          this.loading += 1;
          const response = await fetch(`${config.manualSortUrl}${query}`);
          const sets = await response.json() as ColocSet[];
          this.serverSets = keyBy(sets, 'baseAnnotationId');
          this.loading -= 1;
        } catch (err) {
          console.log(err);
          this.$alert("Could not load previous data. Please tell Lachlan")
          // Leave this.loading set so that they don't overwrite existing data
        }
      }
    }

    makeSet(baseAnnotation: ICBlockAnnotation, setIdx: number): ColocSet | null {
      const rng = new Prando(baseAnnotation.id);
      const anns = this.annotations;

      if (this.datasetId == null || this.user == null || anns.length < 12) return null;
      const otherAnnotations: ICBlockAnnotation[] = [];
      let i = 0;
      while (otherAnnotations.length < 10 && i++ < 1000) {
        const ann = anns[rng.nextInt(0, anns.length-1)];
        if (ann.id !== baseAnnotation.id && !otherAnnotations.some(oa => oa.id === ann.id)) {
          otherAnnotations.push(ann);
        }
      }

      return {
        datasetId: this.datasetId,
        user: this.user,
        source: 'webui',
        dsName: this.allAnnotations![0].dataset.name,
        intThreshold: this.intThreshold,
        isIncomplete: null,
        setIdx,
        baseAnnotationId: baseAnnotation.id,
        baseSf: baseAnnotation.sumFormula,
        baseAdduct: baseAnnotation.adduct,
        baseIonImageUrl: baseAnnotation.isotopeImages[0].url,
        baseAvgInt: this.getAnnotationAvgInt(baseAnnotation),
        otherAnnotations: otherAnnotations.map((ann, otherOriginalIdx) => {
          return {
            otherAnnotationId: ann.id,
            otherSf: ann.sumFormula,
            otherAdduct: ann.adduct,
            otherIonImageUrl: ann.isotopeImages[0].url,
            otherAvgInt: this.getAnnotationAvgInt(ann),
            otherOriginalIdx,
            rank: null,
          };
        }),
      };
    }

    getBlockStyle(idx: number) {
      if (idx === this.currentSetIdx) {
        return {
          position: 'absolute',
          transition: 'all 500ms',
          width: '100%',
          left: '0%',
          opacity: 1,
        };
      } else {
        return {
          position: 'absolute',
          transition: 'all 500ms',
          width: '100%',
          left: idx > this.currentSetIdx ? '100%' : '-100%',
          opacity: 0.01,
          visibility: 'hidden',
          'pointer-events': 'none',
        };
      }
    }
  }
</script>
<style scoped lang="scss">
  .container {
    position: relative;
    box-sizing: border-box;
    margin-left: auto;
    margin-right: auto;
    padding-top: 30px;
    max-width: 1800px;
    height: 100%;
    //overflow-x: hidden;
  }
  .floatingHeaderContainer {
    position: fixed;
    z-index: 100;
    display: flex;
    width: 100%;
    background-color: white;
    top: 0;
    left: 0;
    justify-content: center;
  }
  .floatingHeader {
    max-width: 1800px;
    flex-basis: 100%;
    font-size: 20px;
    display: flex;
    flex-direction: row;
    justify-content: stretch;
    position: relative;
    z-index:100;
    >* {
      flex: 1 1 25%;
      text-align: center;
    }
  }
  .blockContainer {
    position: relative;
    width: 100%;
  }
  a {
    color: rgb(0, 105, 224);
  }
</style>
<style>
  body, #app {
    height: 100%;
  }
</style>
