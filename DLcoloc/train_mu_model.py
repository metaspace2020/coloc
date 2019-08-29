from colocalization.datagen import Iterator, train_transform, null_transform
from colocalization.models import mu_model, ModelCheckpoint
import pandas as pd
import numpy as np
from pathlib import Path
from keras.callbacks import CSVLogger, LearningRateScheduler
from colocalization.utils import train_test_split
from model_utils import get_scheduler


DATA_DIR = Path('Data')
DATA_DF = pd.read_csv(DATA_DIR / 'coloc_gs.csv')

CROP_SZ = 128
EMBD_DIM = 512

FOLD = 1
N_FOLDS = 5

MODEL = mu_model
BATCH_SIZE = 16
VERBOSE = False
INIT_WEIGHTS = 'checkpoints/checkpoint.mu_model.embd512.sz128.fold1-5.69-0.06.hdf5'
MODEL_CHECKPOINT = f'checkpoints/checkpoint.{MODEL.__name__}.embd{EMBD_DIM}.sz{CROP_SZ}.fold{FOLD}-{N_FOLDS}.{{epoch:02d}}-{{val_mean_squared_error:.2f}}.hdf5'
CSV_LOGGER = CSVLogger(f'logs/{MODEL.__name__}.sz{CROP_SZ}.log', append=True)

LR = 1e-4
OPTIMIZER = 'adam'
EPOCHS = 2200
# LR_STEPS = {0: 1e-3, 5: 1e-4, 100: 5e-5}
LR_STEPS = {0: 1e-4}
scheduler = get_scheduler(LR_STEPS)


def train(test_fold, n_folds):
    train_df, test_df = train_test_split(DATA_DF, test_fold=test_fold, n_folds=n_folds)
    model = MODEL(lr=LR, weights=INIT_WEIGHTS, optimizer=OPTIMIZER, embd_dim=EMBD_DIM)
    train_iterator = Iterator(DATA_DIR, train_df, CROP_SZ, augment=train_transform(), target_noise=0.0,
                              shuffle=True, seed=None, infinite_loop=True, batch_size=BATCH_SIZE,
                              verbose=VERBOSE, gen_id='train', output_fname=False)
    val_iterator = Iterator(DATA_DIR, test_df, CROP_SZ, augment=null_transform, target_noise=0.0,
                            shuffle=False, seed=None, infinite_loop=False, batch_size=BATCH_SIZE,
                            verbose=VERBOSE, gen_id='val', output_fname=False)

    x, y = zip(*val_iterator)
    x = np.concatenate(x)
    y = np.concatenate(y)
    validation_data = x, y
    callbacks = [
        ModelCheckpoint(MODEL_CHECKPOINT, monitor='val_mean_squared_error', save_best_only=True,
                        layer_to_save='core_model'),
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
