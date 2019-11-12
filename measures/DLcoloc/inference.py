from datagen import Iterator
from models import xception
import numpy as np
from stats import accuracy
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
MODEL2CLASS = {'xception': xception,
               'pi_model': xception}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data_dir', default=None, help='path to gold standard images')
    parser.add_argument('model_type',
                        default=None,
                        choices=['base', 'pi'],
                        help='model type')
    args = parser.parse_args()
    DATA_DIR = Path(args.data_dir)
    MODEL_TYPE = args.model_type
    MODEL_DIR = Path(CURRENT_DIR / 'models/{}_model'.format(MODEL_TYPE))
    PREDS_DF = PREDS_DIR / 'preds_{}.csv'.format(MODEL_TYPE)
    WEIGHTS = list(MODEL_DIR.glob('*.hdf5'))

    for weights_path in WEIGHTS:
        parse = re.match('checkpoint.(.+).sz([0-9]+).fold([0-9]+)-([0-9]+).', weights_path.parts[-1])
        model_name = parse[1]
        crop_sz = int(parse[2])
        test_fold = int(parse[3])
        n_folds = int(parse[4])
        print(f'Model {model_name}, crop size {crop_sz}, fold {test_fold} of {n_folds}')

        _, test_df = train_test_split(DATA_DF[COLUMNS], test_fold=test_fold, n_folds=n_folds)
        val_iterator = Iterator(DATA_DIR, test_df, crop_sz, target_noise=0.0,
                                shuffle=False, seed=None, infinite_loop=False, batch_size=BATCH_SIZE,
                                verbose=False, gen_id='val', output_fname=False)

        x, y = zip(*val_iterator)
        x = np.concatenate(x)
        y = np.concatenate(y).flatten()

        model_class = MODEL2CLASS[model_name]
        K.clear_session()
        model = model_class(weights=weights_path)
        y_pred = model.predict(x).flatten()

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
