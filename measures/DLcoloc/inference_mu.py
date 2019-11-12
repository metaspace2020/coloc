from datagen import Iterator
from models import mu_model
import numpy as np
from stats import accuracy
from scipy.stats import spearmanr, pearsonr
import pandas as pd
import re
from pathlib import Path
from utils import train_test_split
from keras import backend as K
import matplotlib.pyplot as plt
import os
import argparse


CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PREDS_DIR = Path(CURRENT_DIR / 'prediction')
Path.mkdir(PREDS_DIR, exist_ok=True)

DATA_DF = pd.read_csv(CURRENT_DIR / '../../GS/coloc_gs.csv')
COLUMNS = DATA_DF.columns
BATCH_SIZE = 16

MODEL2CLASS = {'mu_model': mu_model}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data_dir',
                        default=None)
    args = parser.parse_args()
    DATA_DIR = Path(args.data_dir)
    MODEL_TYPE = 'mu'
    MODEL_DIR = Path(CURRENT_DIR / 'models/{}_model'.format(MODEL_TYPE))
    PREDS_DF = PREDS_DIR / 'preds_{}.csv'.format(MODEL_TYPE)
    WEIGHTS = list(MODEL_DIR.glob('*.hdf5'))

    for weights_path in WEIGHTS:
        parse = re.match('checkpoint.(.+).embd([0-9]+).sz([0-9]+).fold([0-9]+)-([0-9]+).', weights_path.parts[-1])
        model_name = parse[1]
        embd_dim = int(parse[2])
        crop_sz = int(parse[3])
        test_fold = int(parse[4])
        n_folds = int(parse[5])
        print(f'Model {model_name}, embd_dim {embd_dim}, crop size {crop_sz}, fold {test_fold} of {n_folds}')

        _, test_df = train_test_split(DATA_DF[COLUMNS], test_fold=test_fold, n_folds=n_folds)
        val_iterator = Iterator(DATA_DIR, test_df, crop_sz, target_noise=0.0,
                                shuffle=False, seed=None, infinite_loop=False, batch_size=BATCH_SIZE,
                                verbose=False, gen_id='val', output_fname=False)

        x, y = zip(*val_iterator)
        x = np.concatenate(x)
        x0 = x[..., [0]]
        x1 = x[..., [1]]
        y = np.concatenate(y).flatten()

        model_class = MODEL2CLASS[model_name]
        K.clear_session()
        model = model_class(weights=MODEL_DIR / weights_path, embd_dim=embd_dim, return_core_model=True)

        feat0 = model.predict(x0)
        feat1 = model.predict(x1)
        y_pred = np.array([1 - pearsonr(f0, f1)[0] for f0, f1 in zip(feat0, feat1)])

        DATA_DF.loc[test_df.index, 'pred'] = y_pred * 10
        np.testing.assert_array_almost_equal(DATA_DF.loc[test_df.index, 'rank'], y * 10)

        accuracy(y * 10, y_pred * 10, f'\nFold {test_fold} accuracy:')

    df_preds = DATA_DF.dropna()
    df_preds.to_csv(PREDS_DF, index=False)
    accuracy(df_preds['rank'], df_preds['pred'], f'\nTotal preds {len(df_preds)}:')

    spearman = []
    for g in df_preds.groupby(['datasetId', 'baseSf']):
        spearman.append(accuracy(g[1]['rank'], g[1]['pred'], verbose=False))
    print(f'\nMean spearman {np.array([s[0] for s in spearman]).mean()}')

    plt.figure()
    plt.hist(np.array([s[0] for s in spearman]))
    plt.show()
