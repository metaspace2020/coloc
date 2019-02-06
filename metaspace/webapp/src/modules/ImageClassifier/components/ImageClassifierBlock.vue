<template>
  <div v-if="numToRender > 0" class="block">
    <div style="display:flex;">
      <div class="referenceImageContainer">
        <div class="referenceImage">
          <h4 class="ranking-number">Reference Image</h4>
          <div class="list-ann">
            <plain-image-loader
              :src="thisSet.baseIonImageUrl"
              :colormap="$route.query.colormap || 'Viridis'"
              :max-height="200"
              :max-width="1"
              :annotImageOpacity="1"
              opticalSrc=""
              opticalImageUrl=""
              opacityMode="constant"
              :showOpticalImage="false"
              style="overflow: hidden;"
            />
          </div>
        </div>
      </div>

      <slot name="intro"/>
    </div>
    <div v-if="thisSet != null" class="list">
      <div v-for="row in rows" class="row">
        <div v-for="(anns, rank) in row" class="ranking" :class="{'has-one': anns.length > 0, 'has-many': anns.length > 1}">
          <h4 class="ranking-number">{{parseInt(rank) + (base1 ? 1 : 0)}} {{rank === '0' ? '(Most colocalized)' : rank === '9' ? '(Least colocalized)' : ''}}</h4>
          <draggable
            v-model="ranking[rank]"
            :options="{direction: 'horizontal', ghostClass: 'ghost', animation: 150, group: 'a'}"
            @start="cancelKeyboardSelection"
            @end="cancelKeyboardSelection"
            class="ranking-draggable">
            <transition-group>
              <div
                v-for="ann in anns.filter(shouldShowAnnotation)"
                :key="ann.otherAnnotationId"
                class="list-ann"
              >
                <plain-image-loader
                  :src="ann.otherIonImageUrl"
                  :colormap="$route.query.colormap || 'Viridis'"
                  :max-height="200"
                  :max-width="anns.length > 1 ? 0.5 : 1"
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
    </div>
    <h4>Unranked</h4>
    <div class="list">
      <draggable
        v-model="unranked"
        :options="{direction: 'horizontal', ghostClass: 'ghost', animation: 150, group: 'a'}"
        @start="cancelKeyboardSelection"
        @end="cancelKeyboardSelection"
        class="ranking-draggable unranked">
        <transition-group>
          <div
            v-for="ann in unranked.filter(shouldShowAnnotation)"
            :key="ann.otherAnnotationId"
            class="list-ann"
          >
            <plain-image-loader
              :src="ann.otherIonImageUrl"
              :colormap="$route.query.colormap || 'Viridis'"
              :max-height="200"
              :max-width="1"
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
  import PlainImageLoader from '../../../components/PlainImageLoader.vue';
  import {ColocItem, ColocSet} from './ICBlockAnnotation';
  import draggable from 'vuedraggable';
  import {fromPairs, range, sortBy} from 'lodash-es';

  @Component({
    components: {
      Intersect,
      PlainImageLoader,
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

    numToRender = 0;
    rangeTen = range(10);
    ranking: ColocItem[][] = [];
    unranked: ColocItem[] = [];


    get rows() {
      return [
        fromPairs(range(5).map(i => ([i, this.ranking[i]]))),
        fromPairs(range(5,10).map(i => ([i, this.ranking[i]]))),
      ];
    }



    created() {
      this.syncRanking();
    }
    mounted() {
      const ignoredPromise = this.gradualRender();
    }

    @Watch('thisSet.annotations')
    syncRanking() {
      console.log('syncRanking');
      if (this.thisSet != null) {
        this.ranking = this.rangeTen.map(i => this.thisSet.otherAnnotations.filter(a => a.rank === i));
        this.unranked = this.thisSet.otherAnnotations.filter(a => !(this.rangeTen as any).includes(a.rank));
      } else {
        this.ranking = this.rangeTen.map(i => []);
        this.unranked = [];
      }
    }

    @Watch('ranking', {deep: true})
    @Watch('unranked', {deep: true})
    syncRankingToSet() {
      this.ranking.forEach((anns, rank) => {
        anns.forEach(ann => { ann.rank = rank; })
      });
      this.unranked.forEach(ann => { ann.rank = null; });
    }

    @Watch('preload')
    @Watch('visible')
    async gradualRender() {
      if (this.visible) {
        this.numToRender = 10;
      } else if (this.preload) {
        while(this.numToRender < 10) {
          await Vue.nextTick();
          await new Promise(resolve => setTimeout(resolve, 100));
          this.numToRender++;
        }
      }
    }

    cancelKeyboardSelection() {
      this.$emit('update:selectedIdx', null);
    }

    shouldShowAnnotation(ann: ColocItem) {
      return this.thisSet && this.thisSet.otherAnnotations.indexOf(ann) <= this.numToRender;
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
  @mixin flexy {
    display: flex;
    flex-direction: row;
    flex: auto;
  }

  .list {
    //margin: -5px;
  }
  .row {
    display: flex;
    flex-flow: row;
    justify-items: stretch;
  }
  .ranking {
    position: relative;
    border: 1px solid grey;
    border-radius: 5px;
    flex: 1 1 20%;
    box-sizing: border-box;
    padding-top: 20px;
    margin: 5px;
  }
  .ranking-number {
    position: absolute;
    left: 4px;
    top: 2px;
  }

  .ranking-draggable {
    height: 100%;
    >span {
      display: flex;
      flex-flow: row wrap;
      justify-items: center;
      justify-content: center;
      align-content: flex-start;
      min-height: 100px;
      height: 100%;
    }
  }
  .unranked >span{
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-start;
    >* {
      //width: 20%;
      padding: 11px
    }
  }

  .list-ann {
    box-sizing: border-box;
    padding: 5px;
    .ranking & {
      flex: 1 1;
    }
    .ranking.has-many & {
      flex: 1 1;
      /*width: 50%;*/
      max-width: 50%;
    }

  }
  .referenceImageContainer {
    width: 20%;
    box-sizing: border-box;
    padding: 5px;
  }
  .referenceImage {
    position: relative;
    box-sizing: border-box;
    padding-top: 20px;
    border: 1px solid black;
    border-radius: 5px;
  }

  h4 {
    line-height: 24px;
    margin-bottom: 10px;
    margin-top: 0;
    font-size: 18px;
  }

  /deep/ .ghost {
    opacity: .5;
    background: #C8EBFB;
    transform: scale(0.5, 0.5);
    transform-origin: center center;
  }
  .selected-item {
    background: #C8EBFB;
  }
</style>
