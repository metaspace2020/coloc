import pandas as pd
import numpy as np
import re
from scipy.stats import spearmanr, kendalltau, pearsonr
import pickle
from pathlib import Path
from colocalization.utils import train_test_split
import lightgbm as lgb
from colocalization.stats import accuracy


FEATURE_DICT = Path('Data/features.ncomp20.naugs40.pkl')
DATA_DF = pd.read_csv('Data/coloc_gs.csv')
PREDS_DF_PATH = 'prediction/preds_gbt5.csv'
FOLDS = range(1, 6)
N_FOLDS = 5

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


def load_data(feature_dict, df, test_fold, n_folds):
    def _comb_features(base_f, other_f):
        return np.concatenate([
            base_f,
            other_f,
            np.square(base_f - other_f),
            [spearmanr(base_f, other_f)[0]],
            # [np.square(base_f - other_f).sum()],
            # [pearsonr(base_f, other_f)[0]],
        ])

    def _get_features(_df):
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
    with open(FEATURE_DICT, 'rb') as f:
        feature_dict = pickle.load(f)

    # parse = re.match('features.ncomp([0-9]+).naugs([0-9]+)', FEATURE_DICT.stem)
    # ncomp = int(parse[1])
    # naugs = int(parse[2])
    # feature_dict = {k: v.reshape(ncomp, naugs).mean(axis=-1) for k, v in feature_dict.items()}

    return _get_features(train_df), _get_features(test_df), test_df.index


def train(x_train: np.array, y_train: np.array, x_val: np.array, y_val: np.array, save_path=None):

    train_data = lgb.Dataset(x_train, label=y_train)
    val_data = lgb.Dataset(x_val, label=y_val)
    gbm = lgb.train(PARAM, train_data, NUM_ROUND, valid_sets=[train_data, val_data], verbose_eval=True)
    pred = gbm.predict(x_val)

    accuracy(y_val, pred)
    return pred


if __name__ == '__main__':
    PREDS_DF = DATA_DF.copy()
    for fold in FOLDS:
        print(f'Fold {fold}/{len(FOLDS)}')
        (train_features, train_y), (test_features, test_y), df_index = load_data(FEATURE_DICT, DATA_DF, fold, N_FOLDS)
        assert len(train_features) + len(test_features) == len(DATA_DF)

        pred = train(train_features, train_y, test_features, test_y)
        PREDS_DF.loc[df_index, 'pred'] = pred * 10

    PREDS_DF.to_csv(PREDS_DF_PATH, index=False)
    accuracy(DATA_DF['rank'], PREDS_DF['pred'])
