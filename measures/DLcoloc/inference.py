from colocalization.datagen import Iterator
from colocalization.models import xception
import numpy as np
from colocalization.stats import accuracy
import pandas as pd
import re
from pathlib import Path
from colocalization.utils import train_test_split
from keras import backend as K
import matplotlib.pyplot as plt


DATA_DIR = Path('Data')
MODEL_DIR = Path('model/pi_model')
DATA_DF = pd.read_csv(DATA_DIR / 'coloc_gs.csv')
PREDS_DF = 'prediction/preds_pi.csv'
COLUMNS = DATA_DF.columns
BATCH_SIZE = 16
WEIGHTS = [
    # 'checkpoint.xception.sz128.fold1-5.78-0.04.hdf5',
    # 'checkpoint.xception.sz128.fold2-5.04-0.05.hdf5',
    # 'checkpoint.xception.sz128.fold3-5.18-0.05.hdf5',
    # 'checkpoint.xception.sz128.fold4-5.08-0.06.hdf5',
    # 'checkpoint.xception.sz128.fold5-5.09-0.06.hdf5',

    'checkpoint.pi_model.sz128.fold1-5.02-0.04.hdf5',   # 80.57
    'checkpoint.pi_model.sz128.fold2-5.01-0.04.hdf5',   # 80.65
    'checkpoint.pi_model.sz128.fold3-5.01-0.04.hdf5',   # 0.7829
    'checkpoint.pi_model.sz128.fold4-5.94-0.07.hdf5',   # 0.6048
    'checkpoint.pi_model.sz128.fold5-5.03-0.05.hdf5',   # 0.7882
]

MODEL2CLASS = {'xception': xception,
               'pi_model': xception}


if __name__ == '__main__':

    for weights_path in WEIGHTS:
        parse = re.match('checkpoint.(.+).sz([0-9]+).fold([0-9]+)-([0-9]+).', weights_path)
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
        model = model_class(weights=MODEL_DIR / weights_path)
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
