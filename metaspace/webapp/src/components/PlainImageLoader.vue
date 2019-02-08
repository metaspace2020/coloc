<template>
  <div class="image-loader"
       v-loading="isLoading"
       ref="parent">

    <div :style="containerStyle">
      <div :style="imageStyle" />
    </div>

    <canvas ref="canvas" style="display:none;"></canvas>
  </div>
</template>

<script>
 // uses loading directive from Element-UI

 import createColormap from '../lib/createColormap';
 import {quantile} from 'simple-statistics';
 import config from '../clientConfig-coloc.json';
 import resize from 'vue-resize-directive';
 import {throttle} from 'lodash-es';


 export default {
   directives: {
     resize
   },
   props: {
     src: {
       type: String
     },
     maxHeight: {
       type: Number,
       default: 500
     },
     maxWidth: {
       type: Number,
       default: 1
     },
     colormap: {
       type: String,
       default: 'Viridis'
     },
     opticalSrc: {
       type: String,
       default: null
     },
     annotImageOpacity: {
       type: Number,
       default: 0.5
     },
     zoom: {
       type: Number,
       default: 1
     },
     xOffset: { // in natural IMS image pixels
       type: Number,
       default: 0
     },
     yOffset: {
       type: Number,
       default: 0
     },
     opacityMode: {
       type: String,
       default: 'constant'
     },
     transform: {
       type: String,
       default: ''
     },
     scrollBlock: {
       type: Boolean,
       default: false
     },
     pixelSizeX: {
       type: Number,
       default: 0
     },
     pixelSizeY: {
       type: Number,
       default: 0
     },
     showScaleBar: {
       type: Boolean,
       default: true
     }
   },
   data () {
     return {
       image: new Image(),
       colors: createColormap(this.colormap),
       isLoading: false,
       dataURI: '',
       hotspotRemovalQuantile: 0.99,
       isLCMS: false,
       scaleFactor: 1,

       cellWidth: 0,

       imageWidth: 0,
       imageHeight: 0,
       tmId: 0,
     }
   },
   created() {
     this.onResize();
   },
   mounted() {
     this.image.onload = this.redraw.bind(this);
     this.image.onerror = this.image.onabort = this.onFail.bind(this);
     if (this.src)
       this.loadImage(this.src);
     this.onResize = throttle(this.onResize, 100)
     window.addEventListener('resize', this.onResize);
   },
   beforeDestroy() {
     window.removeEventListener('resize', this.onResize);
   },
   computed: {
     idealWidth() {
       return this.maxHeight != null
         ? Math.min(this.maxWidth * this.cellWidth, this.imageWidth / this.imageHeight * this.maxHeight) + 'px'
         : undefined;
     },
     containerStyle() {
       return {
         // position: 'relative',
         // width: '100%',
         maxWidth: this.idealWidth,
         width: this.idealWidth,
         // maxHeight: this.maxHeight + 'px',
         // padding: `0 0 ${this.imageHeight / this.imageWidth * 100}% 0`,
         // backgroundImage: `url(${this.dataURI})`,
         // backgroundSize: 'contain',
         // backgroundPosition: 'center',
         // backgroundRepeat: 'no-repeat',
       };
     },
     imageStyle() {
       return {
         position: 'relative',
         width: '100%',
         maxWidth: this.idealWidth,
         maxHeight: this.maxHeight + 'px',
         padding: `0 0 ${this.imageHeight / this.imageWidth * 100}% 0`,
         backgroundImage: `url(${this.dataURI})`,
         backgroundSize: 'contain',
         backgroundPosition: 'center',
         backgroundRepeat: 'no-repeat',
       };
     },

   },
   watch: {
     'src' (url) {
       this.loadImage(url);
     },
     'colormap' (name) {
       this.colors = createColormap(name);
       this.applyColormap();
     }
   },
   methods: {
     onResize() {
       this.cellWidth = (Math.min(window.innerWidth, 1800) - 150) / 5;
     },

     loadImage(url) {
       this.image.crossOrigin = "Anonymous";
       this.image.src = (config.imageStorage || '') + url;
       if (window.navigator.userAgent.includes("Trident")) {
         // IE11 never fires the events that would set isLoading=false.
         // It's probably this: https://stackoverflow.com/questions/16797786/image-load-event-on-ie
         // but this issue isn't big enough to justify the time cost and risk of destabilizing to try a solution.
         return;
       }

       this.isLoading = true;
     },

     computeQuantile () {
       let canvas = this.$refs.canvas,
           ctx = canvas.getContext("2d");

       let data = [],
           imageData = ctx.getImageData(0, 0, canvas.width, canvas.height),
           grayscaleData = imageData.data;

       for (let i = 0; i < grayscaleData.length; i += 4)
         if (grayscaleData[i] > 0)
           data.push(grayscaleData[i])

       if (data.length > 0)
         return quantile(data, this.hotspotRemovalQuantile);
       else
         return 0;
     },

     removeHotspots(imageData, q) {
       let grayscaleData = imageData.data;

       if (this.hotspotRemovalQuantile < 1) {
         for (let i = 0; i < grayscaleData.length; i += 4) {
           let value = 255;
           if (grayscaleData[i] < q)
             value = Math.floor(grayscaleData[i] * 255 / q);

           // set r,g,b channels
           grayscaleData[i] = value;
           grayscaleData[i + 1] = value;
           grayscaleData[i + 2] = value;
         }
       }

       this.grayscaleData = grayscaleData;
     },

     redraw () {
       this.updateDimensions();
       this.isLCMS = this.image.height === 1;
       const canvas = this.$refs.canvas;
       if (canvas != null) {
         const ctx = canvas.getContext("2d");

         ctx.canvas.height = this.image.naturalHeight;
         ctx.canvas.width = this.image.naturalWidth;
         ctx.setTransform(1, 0, 0, 1, 0, 0);

         ctx.drawImage(this.image, 0, 0);
         const q = this.computeQuantile();

         ctx.drawImage(this.image, 0, 0);
         if (canvas.width === 0)
           return;
         let imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
         this.removeHotspots(imageData, q);
         ctx.putImageData(imageData, 0, 0);
         this.applyColormap();

         this.isLoading = false;
       }
     },

     applyColormap() {
       let canvas = this.$refs.canvas,
           ctx = canvas.getContext("2d");

       var g = this.grayscaleData;
       if (g === undefined || canvas.width === 0)
         return;

       var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
       var pixels = imageData.data;
       var numPixels = pixels.length / 4;
       const colors = this.colors.slice();

       for (let i = 0; i < numPixels; i++) {
         let c = colors[g[i*4]];
         pixels[i*4] = c[0];
         pixels[i*4+1] = c[1];
         pixels[i*4+2] = c[2];
         pixels[i*4+3] = g[i*4+3] === 0 ? 0 : 255;
       }

       ctx.clearRect(0, 0, canvas.width, canvas.height);
       ctx.putImageData(imageData, 0, 0);

       this.dataURI = canvas.toDataURL('image/png');
     },

     updateDimensions() {
       this.imageHeight = this.image.naturalHeight;
       this.imageWidth = this.image.naturalWidth;
     },

     onFail () {
       let canvas = this.$refs.canvas,
           ctx = canvas.getContext("2d");
       canvas.width = canvas.height = 0;
       ctx.clearRect(0, 0, canvas.width, canvas.height);
       this.isLoading = false;
       this.dataURI = '';
     },
   }
 }
</script>

<style lang="scss">
 /* No attribute exists for MS Edge at the moment, so ion images are antialiased there */
 .isotope-image {
   image-rendering: pixelated;
   image-rendering: -moz-crisp-edges;
   -ms-interpolation-mode: nearest-neighbor;
   user-select: none;
 }

 .image-loader {
   display: flex;
   flex-direction: column;
   align-content: center;
   justify-content: space-evenly;
   overflow: hidden;
   cursor: -webkit-grab;
   cursor: grab;
   width: 100%;
   line-height: 0;
 }

 .image-loader__overlay-text {
   font: 24px 'Roboto', sans-serif;
   display: block;
   position: relative;
   text-align: center;
   top: 50%;
   transform: translateY(-50%);
   color: #fff;
   padding: auto;
 }

 .image-loader__overlay {
  pointer-events: none;
  background-color: #fff;
  width: 100%;
  height: 100%;
  position: absolute;
  opacity: 0;
  transition: 1.1s;
 }

 .image-loader__overlay--visible {
  background-color: black;
  opacity: 0.6;
  transition: 0.7s;
 }

 .pixelSizeX {
   color: var(--scaleBar-color);
   position: absolute;
   font-weight: bold;
   width: var(--scaleBarX-size);
   bottom: 20px;
   left: 20px;
   border-bottom: 5px solid var(--scaleBar-color);
   z-index: 3;
 }

 .pixelSizeXText {
   position: absolute;
   width: var(--scaleBarTextWidth);
   bottom: 10px;
   left: 0;
   right: 0;
   text-align: center;
   z-index: 3;
 }

 .pixelSizeY {
   color: var(--scaleBar-color);
   position: absolute;
   font-weight: bold;
   height: var(--scaleBarY-size);
   bottom: 20px;
   left: 20px;
   border-left: 5px solid var(--scaleBar-color);
   z-index: 3;
 }

 .pixelSizeYText {
   position: absolute;
   content: "";
   width: 100px;
   bottom: var(--addedValToOyBar)px;
   top: 5px;
   left: 3px;
   right: 0;
   z-index: 3;
 }

 .pixelSizeX:hover,
 .pixelSizeY:hover {
   cursor: pointer;
 }

 .color-picker {
   display: block;
   position: absolute;
   bottom: 35px;
   left: 30px;
   z-index: 4;
 }
</style>
