<template>
  <div v-if="isPreloaded" class="block">
    <div class="referenceImage">
      <h4>Reference Image</h4>
      <image-loader
        :src="thisSet.baseIonImageUrl"
        :colormap="$route.query.colormap || 'Viridis'"
        :max-height="184"
        :annotImageOpacity="1"
        opticalSrc=""
        opticalImageUrl=""
        opacityMode="constant"
        :showOpticalImage="false"
        style="overflow: hidden;"
      />
    </div>
    <div>
      <draggable
        v-if="thisSet != null"
        v-model="thisSet.otherAnnotations"
        :options="{direction: 'horizontal', ghostClass: 'ghost', animation: 150}"
        @start="cancelKeyboardSelection"
        @end="cancelKeyboardSelection">
        <transition-group class="list">
          <div
            v-for="(ann, idx) in thisSet.otherAnnotations"
            :key="ann.otherAnnotationId"
            :class="{'selected-item': idx === selectedIdx}"
          >
            <h4>{{idx + (base1 ? 1 : 0)}}</h4>
            <image-loader
              :src="ann.otherIonImageUrl"
              :colormap="$route.query.colormap || 'Viridis'"
              :max-height="184"
              :annotImageOpacity="1"
              opticalSrc=""
              opticalImageUrl=""
              opacityMode="constant"
              :showOpticalImage="false"
              style="overflow: hidden;"
            />
          </div>
        </transition-group>
      </draggable>
    </div>
  </div>
</template>
<script lang="ts">
  import Vue from 'vue';
  import {Component, Prop, Watch} from 'vue-property-decorator';
  import Intersect from 'vue-intersect';
  import ImageLoader from '../../../components/ImageLoader.vue';
  import {ColocSet} from './ICBlockAnnotation';
  import draggable from 'vuedraggable';

  @Component({
    components: {
      Intersect,
      ImageLoader,
      draggable,
    },
  })
  export default class ImageClassifierBlock extends Vue {
    @Prop({ default: 'Viridis' })
    colormap!: string;
    @Prop()
    thisSet!: ColocSet;
    @Prop({ default: true })
    visible!: boolean;
    @Prop({ default: false })
    preload!: boolean;
    @Prop()
    selectedIdx!: number;
    @Prop({ default: false })
    base1!: boolean;

    isPreloaded = false;

    mounted() {
      this.isPreloaded = this.preload;
    }

    @Watch('preload')
    @Watch('visible')
    setIsPreloaded() {
      if (this.preload || this.visible) {
        this.isPreloaded = true;
      }
    }

    cancelKeyboardSelection() {
      this.$emit('update:selectedIdx', null);
    }
  }
</script>
<style scoped lang="scss">
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

  .list {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    > * {
      display: flex;
      flex-direction: column;
      flex: 0 0 20%;
      box-sizing: border-box;
      padding: 5px;
    }
  }
  .referenceImage {
    width: 300px;
    margin-left: auto;
    margin-right: auto;
  }

  /deep/ .ghost {
    opacity: .5;
    background: #C8EBFB;
  }
  .selected-item {
    background: #C8EBFB;
  }
</style>
