import pandas as pd
import numpy as np
from scipy.stats import spearmanr, kendalltau, pearsonr
import pickle
from pathlib import Path
from utils import train_test_split
import lightgbm as lgb
from stats import accuracy
import os
import argparse


CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PREDS_DIR = Path(CURRENT_DIR / 'prediction')
Path.mkdir(PREDS_DIR, exist_ok=True)

DATA_DF = pd.read_csv(CURRENT_DIR / '../../GS/coloc_gs.csv')

FOLDS = range(1, 6)
N_FOLDS = len(FOLDS)

# LightGBM
LEARNING_RATE = 0.01
NUM_ROUND = 800
PARAM = {
    'objective': 'mse',
    'metric': ['mse'],
    'verbose': 0,
    'learning_rate': LEARNING_RATE,
    'num_leaves': 10,
    'feature_fraction': 0.95,
    'bagging_fraction': 0.95,
    'bagging_freq': 5,
    'max_depth': 11,
    'feature_fraction_seed': 0,
    'bagging_seed': 0,
}


def load_data(feature_dict_path, df, test_fold, n_folds):
    def _comb_features(base_f, other_f):
        return np.concatenate([
            base_f,
            other_f,
            np.square(base_f - other_f),
            [spearmanr(base_f, other_f)[0]],
            # [np.square(base_f - other_f).sum()],
            # [pearsonr(base_f, other_f)[0]],
        ])

    def _get_features(_df, feature_dict):
        features = []
        y = []
        for _, row in _df.iterrows():
            datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row
            base_ion = '.'.join((baseSf, baseAdduct.replace('+', 'p').replace('-', 'm')))
            other_ion = '.'.join((otherSf, otherAdduct.replace('+', 'p').replace('-', 'm')))
            base_img = '.'.join((datasetId, base_ion))
            other_img = '.'.join((datasetId, other_ion))

            base_features = feature_dict[next(key for key in feature_dict.keys() if base_img in key)]
            other_features = feature_dict[next(key for key in feature_dict.keys() if other_img in key)]
            features.append(_comb_features(base_features, other_features))
            y.append(rank / 10.)
        return np.array(features), np.array(y)

    train_df, test_df = train_test_split(df, test_fold=test_fold, n_folds=n_folds)
    with open(feature_dict_path, 'rb') as f:
        feature_dict = pickle.load(f)

    return _get_features(train_df, feature_dict), _get_features(test_df, feature_dict), test_df.index


def train(x_train: np.array, y_train: np.array, x_val: np.array, y_val: np.array, save_path=None):

    train_data = lgb.Dataset(x_train, label=y_train)
    val_data = lgb.Dataset(x_val, label=y_val)
    gbm = lgb.train(PARAM, train_data, NUM_ROUND, valid_sets=[train_data, val_data], verbose_eval=True)
    pred = gbm.predict(x_val)

    accuracy(y_val, pred)
    return pred


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-features', default=None, required=False, help='path to unsupervised features')
    args = parser.parse_args()
    MODEL_TYPE = 'gbt'

    MODEL_DIR = Path(CURRENT_DIR / 'models/unsupervised_model')
    FEATURE_DICT_PATH = Path(args.features) if args.features else MODEL_DIR / 'features.ncomp20.naugs40.pkl'
    PREDS_DF_PATH = PREDS_DIR / 'preds_{}.csv'.format(MODEL_TYPE)

    PREDS_DF = DATA_DF.copy()
    for fold in FOLDS:
        print(f'Fold {fold}/{len(FOLDS)}')
        (train_features, train_y), (test_features, test_y), df_index = load_data(FEATURE_DICT_PATH, DATA_DF,
                                                                                 fold, N_FOLDS)
        assert len(train_features) + len(test_features) == len(DATA_DF)

        pred = train(train_features, train_y, test_features, test_y)
        PREDS_DF.loc[df_index, 'pred'] = pred * 10

    PREDS_DF.to_csv(PREDS_DF_PATH, index=False)
    accuracy(DATA_DF['rank'], PREDS_DF['pred'])
