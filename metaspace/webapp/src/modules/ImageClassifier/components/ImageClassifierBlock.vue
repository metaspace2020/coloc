<template>
  <intersect @change="handleVisibilityChange" :threshold="[0,0]" rootMargin="2000px">
    <div v-loading="loading">
      <div v-for="(row, idx) in rows"
           :key="idx"
           class="row">
        <div v-for="annotation in row"
             v-if="isVisible && annotation != null"
             :key="annotation.id"
             :data-key="annotation.id"
             :class="getAnnotationClass(annotation.id)"
             @mouseenter="e => $emit('mouseenter', Object.assign(e, {annotation}))"
             @mouseleave="e => $emit('mouseleave', Object.assign(e, {annotation}))"
        >
          <image-loader :src="annotation.isotopeImages[0].url"
                        :colormap="colormap"
                        :max-height="184"
                        :annotImageOpacity="1"
                        opticalSrc=""
                        opticalImageUrl=""
                        opacityMode="constant"
                        :showOpticalImage="false"
                        style="overflow: hidden;"
            />
          <div class="subtitle">
            <div>{{annotation.sumFormula}}</div>
            <div>{{ parseFloat(annotation.mz).toFixed(4) }}</div>
          </div>
        </div>
        <div v-else />
      </div>
      <hr />
    </div>
  </intersect>
</template>
<script lang="ts">
  import Vue from 'vue';
  import { Component, Prop } from 'vue-property-decorator';
  import {chunk, debounce} from 'lodash-es';
  import Intersect from 'vue-intersect';
  import ImageLoader from '../../../components/ImageLoader.vue';
  import { ICBlockAnnotation } from './ICBlockAnnotation';

  type AnnotationLabel = undefined | 1 | 2 | 3 | 4; // none / on- / off- / ind / error

  @Component({
    components: {
      Intersect,
      ImageLoader,
    },
  })
  export default class ImageClassifierBlock extends Vue {
    constructor() {
      super();
      this.handleVisibilityChange = debounce(this.handleVisibilityChange, 1000);
    }
    @Prop({ default: 'Viridis' })
    colormap!: string;
    @Prop()
    numCols!: number;
    @Prop()
    annotationLabels!: Record<string, AnnotationLabel>;
    @Prop()
    annotations!: ICBlockAnnotation[];

    loading = 0;
    isVisible = false;

    get rows(): (ICBlockAnnotation | null)[][] {
      const rows = chunk(this.annotations, this.numCols) as (ICBlockAnnotation | null)[][];
      // Pad rows so they're all the same width
      rows.forEach(row => {
        while (row.length < this.numCols) {
          row.push(null);
        }
      });
      return rows;
    }

    getAnnotationClass(id: string) {
      const label = this.annotationLabels[id];
      return {
        'annotation': true,
        'onsample': label === 1,
        'offsample': label === 2,
        'indeterminate': label === 3,
      }
    }

    handleVisibilityChange(intersection: IntersectionObserverEntry[]) {
      this.isVisible = intersection[0].isIntersecting;
    }
  }
</script>
<style scoped lang="scss">
  .row {
    width: 100%;
    height: 250px;
    display: flex;
  }
  .annotation {
    height: 234px;
    max-width: 300px;
    flex: 1 1 200px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    margin: 8px;

    &.onsample {
      background-color: #CCFFCC;
    }
    &.offsample {
      background-color: #FFCCCC;
    }
    &.indeterminate {
      background-color: #FFFFCC;
    }
    &.error {
      background-color: #FF0000;
    }
  }

  .subtitle {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    > * {
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      word-break: break-all;
      margin: 0 4px;
    }
  }
</style>
