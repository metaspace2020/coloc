from colocalization.datagen import Iterator, train_transform
from colocalization.models import xception
import numpy as np
import pandas as pd
from pathlib import Path
from keras.callbacks import ModelCheckpoint, CSVLogger, LearningRateScheduler
from colocalization.utils import train_test_split
from model_utils import get_scheduler


DATA_DIR = Path('Data')
DATA_DF = pd.read_csv(DATA_DIR / 'coloc_gs_.csv')

CROP_SZ = 128
FOLD = 5
N_FOLDS = 5

MODEL = xception
BATCH_SIZE = 16
VERBOSE = False
INIT_WEIGHTS = None
# INIT_WEIGHTS = 'checkpoints/checkpoint.xception.sz128.fold5-5.31-0.06.hdf5'
MODEL_CHECKPOINT = f'checkpoints/checkpoint.{MODEL.__name__}.sz{CROP_SZ}.fold{FOLD}-{N_FOLDS}.{{epoch:02d}}-{{val_mean_squared_error:.2f}}.hdf5'
CSV_LOGGER = CSVLogger(f'logs/{MODEL.__name__}.sz{CROP_SZ}.log', append=True)

LR = 1e-4
OPTIMIZER = 'adam'
EPOCHS = 320
LR_STEPS = {0: 1e-3, 10: 1e-4, 100: 5e-5}
# LR_STEPS = {0: 5e-5}
scheduler = get_scheduler(LR_STEPS)


def train(test_fold, n_folds):
    train_df, test_df = train_test_split(DATA_DF, test_fold=test_fold, n_folds=n_folds)
    model = MODEL(lr=LR, weights=INIT_WEIGHTS, optimizer=OPTIMIZER)

    train_iterator = Iterator(DATA_DIR, train_df, CROP_SZ, augment=train_transform(), target_noise=0.05,
                              shuffle=True, seed=None, infinite_loop=True, batch_size=BATCH_SIZE,
                              verbose=VERBOSE, gen_id='train', output_fname=False)
    val_iterator = Iterator(DATA_DIR, test_df, CROP_SZ, augment=None, target_noise=0.0,
                            shuffle=False, seed=None, infinite_loop=False, batch_size=BATCH_SIZE,
                            verbose=VERBOSE, gen_id='val', output_fname=False)

    x, y = zip(*val_iterator)
    x = np.concatenate(x)
    y = np.concatenate(y)
    validation_data = x, y
    callbacks = [
        ModelCheckpoint(MODEL_CHECKPOINT, monitor='val_mean_squared_error', save_best_only=True),
        CSV_LOGGER,
        LearningRateScheduler(scheduler)
    ]
    model.fit_generator(
        train_iterator,
        steps_per_epoch=len(train_df) // BATCH_SIZE,
        epochs=EPOCHS,
        validation_data=validation_data,
        workers=3,
        callbacks=callbacks
    )


if __name__ == '__main__':
    train(test_fold=FOLD, n_folds=N_FOLDS)
