# Co-localization measures based on Deep Learning methods

## Requirements

* python 3.x
* keras, umap, lightgbm packages
* sklearn, scipy, numpy, pandas packages
* cv2, albumentations packages

## Setup

* download pre-trained models and features from [here](https://oc.embl.de/index.php/s/M7sVyqehsJwTXcM)
* unzip `models_coloc.zip` into `measures/DLcoloc/models` preserving directory structure  

## Run

* cd `measures/DLcoloc`
* for `base` and `pi`  models run:  
    `python inference.py <data path> <model type: base|pi>`  
* for `mu` model run:  
    `python inference_mu.py <data path>`
* for `unsupervised` model run:  
    `python train_unsupervised_model.py  <data path> [-dump_features]`  
   `-dump_features` argument is only required if you want to save features for later use with tree model. Not required as unsupervised features already provided as `features.ncomp20.naugs40.pkl`
* for `gbt` model run:  
    `python train_tree_model.py [-features=<path to unsupervised features>]`  
    by default unsupervised features `features.ncomp20.naugs40.pkl` is used
* resulting predictions will be saved in `measures/DLcoloc/prediction`  
  
EXAMPLE:  
  `python inference.py F:/Sandbox/coloc/Data base`
