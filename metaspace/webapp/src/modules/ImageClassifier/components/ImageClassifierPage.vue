<template>
  <div
    ref="container"
    class="container"
    v-loading="loading"
  >
    <div class="floatingHeaderContainer" v-if="!loading">
      <div class="floatingHeader">
        <div style="background-color: #FFCCCC; cursor: pointer;flex: 0 1 200px" @click="goBack()">&lsaquo; Save & Go Back</div>
        <div v-if="currentSetIdx < filteredRouteSets.length" :title="currentSet && currentSet.id">
          {{ currentSetIdx+1 }} out of {{ filteredRouteSets.length }}
          <span style="white-space: nowrap">({{ currentSet && currentSet.datasetId }}:{{ routeSets[currentSetIdx].setIdx }},</span>
          <span style="white-space: nowrap">{{ currentSet && (currentSet.baseSf + currentSet.baseAdduct) }})</span>
        </div>
        <div v-else>FINISHED</div>
        <div v-if="currentSetIdx < filteredRouteSets.length" style="flex: 0 1 120px">
          <el-checkbox v-model="currentSetIsIncomplete" label="Incomplete" />
        </div>
        <div style="background-color: #CCFFCC; cursor: pointer;flex: 0 1 200px" @click="goForward()">Save & Continue &rsaquo;</div>
      </div>
    </div>
    <div class="header">
      <div v-show="showfilters">
        <filter-panel level="imageclassifier" />
      </div>
    </div>
    <div class="blockContainer">
      <image-classifier-block
        v-if="!loading"
        v-for="(cs, setIdx) in filteredColocSets"
        :key="cs.baseAnnotationId"
        :thisSet="cs"
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
            If multiple images have the same degree of colocalization, put them in the same rank box.
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
      <div v-if="!loading && routeSets.length === 0">
        No dataset found, or not enough annotations matching filters
      </div>
      <div v-if="!loading && currentSetIdx === filteredRouteSets.length">
        <div v-if="filterCompleted && filteredRouteSets.length === 0">
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
  import {
    castArray,
    cloneDeep,
    debounce,
    filter,
    flatMap,
    forEach,
    fromPairs, groupBy,
    isEqual,
    keyBy,
    range,
    uniq, zip,
  } from 'lodash-es';
  import {quantile} from 'simple-statistics';
  import Prando from 'prando';
  import { ColocSet, ICBlockAnnotation, ICBlockAnnotationsQuery } from './ICBlockAnnotation';
  import './importTool';
  import {FilterPanel} from '../../Filters';
  import draggable from 'vuedraggable';
  import ImageLoader from '../../../components/PlainImageLoader.vue';
  import {flatten} from 'fast-glob/out/utils/array';

  interface RouteSet {
    datasetId: string;
    setIdx: number;
    globalIdx: number;
  }

  const qs = (obj: object) => '?' + Object.entries(obj)
    .map(([key, val]) => `${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
    .join('&');

  @Component<ImageClassifierPage>({
    components: {
      ImageClassifierBlock,
      ImageLoader,
      FilterPanel,
      draggable
    },
  })
  export default class ImageClassifierPage extends Vue {
    loading = 0;
    dsAnnotations: Record<string, ICBlockAnnotation[]> = {};
    allAnnotations: ICBlockAnnotation[] = [];
    serverSets: Record<string, ColocSet | null> = {};
    clientSets: Record<string, ColocSet | null> = {};
    selectedIdx: number | null = null;
    base1 = true;
    filterCompleted = false;
    lastCompletedAnnotationIds: string[] = [];

    created() {
      let ignoredPromise = this.loadSets();
      // Debounce because HMR often causes many copies of the same listener
      // this.handleKeyPress = debounce(this.handleKeyPress, 10);
      // this.handleKeyDown = debounce(this.handleKeyDown, 10);
    }
    // mounted() {
    //   document.addEventListener('keypress', this.handleKeyPress, true);
    //   document.addEventListener('keydown', this.handleKeyDown, true);
    // }
    // beforeDestroy() {
    //   document.removeEventListener('keypress', this.handleKeyPress);
    //   document.removeEventListener('keydown', this.handleKeyDown);
    // }

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
    filter: any = {};
    query: any = {};
    data() {
      return {
        filter: cloneDeep(this.$store.getters.filter),
        query: cloneDeep(this.$route.query),
      }
    }
    @Watch('this.$store.getters.filter')
    @Watch('this.$route.query')
    lazyUpdate() {
      ([['filter', this.$store.getters.filter], ['query', this.$route.query]] as any).forEach(([prop, src]: any) => {
        const dest = (this as any)[prop] as any;
        Object.entries(src).forEach(([k,v]: any) => {
          if (dest[k] !== v) {
            dest[k] = v as any;
          }
        });
        Object.keys(dest as any).forEach((k: any) => {
          if (!(k in src)) {
            delete dest[k];
          }
        });
      })
    }

    get filters() {
      return this.$store.getters.gqlAnnotationFilter;
    }

    get user(): string | null { return this.filter.user; }
    get pix() { return parseFloat(this.query.pix) || 0; }
    get showfilters(): boolean { return !!this.query.showfilters; }
    get querySets(): string { return this.query.sets || ''; }
    get querySets2(): string { console.log(this.querySets); return this.querySets; }
    get routeSets(): RouteSet[] {
      const param = this.querySets2.split(';') as string[];
      const routeSets = flatMap(param, set => {
        const [datasetId, setIdxs] = set.split(':');
        const allIdxs = flatMap<string, number>(setIdxs.split(','), idxs => {
          if (idxs.includes('-')) {
            const [lo, hi] = idxs.split('-');
            return range(parseInt(lo, 10) | 0, (parseInt(hi, 10) | 0) + 1);
          } else {
            return [parseInt(idxs, 10) | 0];
          }
        });
        return allIdxs.map(setIdx => ({ datasetId, setIdx }));
      });
      const b = Object.values(groupBy(routeSets, 'datasetId'));
      console.log({b, zip: zip(...b)})
      const c = filter(flatten(flatten(zip(...b)) as any));
      // Interleave datasets
      return c.map((set, globalIdx) => ({ ...set, globalIdx })) as any as RouteSet[];
    }
    get filteredRouteSets(): RouteSet[] {
      return this.routeSets
        .filter(({datasetId, setIdx}) => {
          const ds = this.dsAnnotations[datasetId];
          const ann = ds && ds[setIdx];
          return ann != null && (!this.filterCompleted || !this.lastCompletedAnnotationIds.includes(ann.id));
        });
    }
    get filteredColocSets(): ColocSet[] {
      return this.filteredRouteSets.map(rs => this.getSetById(rs)!);
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
      return this.getSetById(this.filteredRouteSets[setIdx]);
    }
    getSetById(routeSet: RouteSet): ColocSet | null {
      const annotation = this.dsAnnotations[routeSet.datasetId][routeSet.setIdx];
      if (annotation != null) {
        const annotationId = annotation.id;
        if (this.clientSets[annotationId] == null) {
          if (this.serverSets[annotationId] != null) {
            Vue.set(this.clientSets, annotationId, cloneDeep(this.serverSets[annotationId]));
          } else {
            Vue.set(this.clientSets, annotationId, this.makeSet(annotation, routeSet.setIdx));
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

    // handleKeyDown(event: KeyboardEvent) {
    //   if ((event.target as HTMLElement).closest('input') == null) {
    //     if (event.key === 'ArrowLeft') {
    //       this.goBack();
    //       event.preventDefault();
    //     } else if (event.key === 'ArrowRight') {
    //       this.goForward();
    //       event.preventDefault();
    //     }
    //   }
    // }
    //
    // handleKeyPress(event: KeyboardEvent) {
    //   if ((event.target as HTMLElement).closest('input') == null) {
    //     const idx = (this.base1 ? '1234567890' : '0123456789').indexOf(event.key);
    //     if (idx !== -1) {
    //       if (this.selectedIdx == null) {
    //         this.selectedIdx = idx;
    //         event.preventDefault();
    //       } else if (this.currentSet != null && this.currentSet.otherAnnotations.length === 10) {
    //         console.log('swapping', this.selectedIdx, idx, this.currentSet);
    //         const ann = this.currentSet.otherAnnotations.splice(this.selectedIdx, 1)[0];
    //         this.currentSet.otherAnnotations.splice(idx, 0, ann);
    //         this.selectedIdx = null;
    //         event.preventDefault();
    //       }
    //     }
    //   }
    // }

    toggleFilterCompleted() {
      const ignoredPromise = this.save();
      if (!this.filterCompleted) {
        this.lastCompletedAnnotationIds = this.routeSets
          .map((rs) => this.getSetById(rs))
          .filter(set => set != null && !this.isSetIncomplete(set))
          .map(set => set!.baseAnnotationId);
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
      if (this.currentSetIdx < this.filteredRouteSets.length) {
        this.currentSetIdx++;
      }
      this.selectedIdx = null;
    }

    async save() {
      const setIdx = this.currentSetIdx;
      if (setIdx === this.filteredRouteSets.length) return;
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

    @Watch('routeSets')
    @Watch('user')
    async loadSets() {
      const datasetIds = uniq(this.routeSets.map(rs => rs.datasetId));
      console.log(this.routeSets)
      const user = this.user;

      if (datasetIds.length > 0 && user) {
        try {
          this.loading += 1;
          const setsPromise = Promise.all(datasetIds.map(async datasetId => {
            const query = qs({ datasetId, user });
            const response = await fetch(`${config.manualSortUrl}${query}`);
            return await response.json() as ColocSet[];
          }));
          const annotationsQuery = qs({datasetIds, filter: JSON.stringify(this.filters), pix: this.pix });
          const annotationsPromise = await fetch(`${config.manualSortUrl}/annotations${annotationsQuery}`);
          const [sets, annotationsResponse] = await Promise.all([setsPromise, annotationsPromise]);
          const annotations = await annotationsResponse.json();
          this.serverSets = keyBy(flatten(sets), 'baseAnnotationId');
          this.dsAnnotations = annotations;
          this.allAnnotations = flatMap(annotations, 'annotations');
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
      const anns = this.dsAnnotations[baseAnnotation.dataset.id];

      if (this.user == null || anns.length < 12) return null;
      const otherAnnotations: ICBlockAnnotation[] = [];
      let i = 0;
      while (otherAnnotations.length < 10 && i++ < 1000) {
        const ann = anns[rng.nextInt(0, anns.length-1)];
        if (ann.id !== baseAnnotation.id && !otherAnnotations.some(oa => oa.id === ann.id)) {
          otherAnnotations.push(ann);
        }
      }

      return {
        datasetId: baseAnnotation.dataset.id,
        user: this.user,
        source: 'webui',
        dsName: baseAnnotation.dataset.name,
        pixelFillRatioThreshold: this.pix,
        isIncomplete: null,
        setIdx,
        baseAnnotationId: baseAnnotation.id,
        baseSf: baseAnnotation.sumFormula,
        baseAdduct: baseAnnotation.adduct,
        baseIonImageUrl: baseAnnotation.isotopeImages[0].url,
        basePixelFillRatio: baseAnnotation.pixelFillRatio,
        otherAnnotations: otherAnnotations.map((ann, otherOriginalIdx) => {
          return {
            otherAnnotationId: ann.id,
            otherSf: ann.sumFormula,
            otherAdduct: ann.adduct,
            otherIonImageUrl: ann.isotopeImages[0].url,
            otherPixelFillRatio: ann.pixelFillRatio,
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
