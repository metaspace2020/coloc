from colocalization.datagen import IteratorPi, train_transform
from colocalization.models import pi_model, ModelCheckpoint
import numpy as np
import pandas as pd
from pathlib import Path
from keras.callbacks import CSVLogger, LearningRateScheduler
from colocalization.utils import train_test_split
from model_utils import get_scheduler


DATA_DIR = Path('Data')
DATA_DF = pd.read_csv(DATA_DIR / 'coloc_gs.csv')
DATA_DIR_UNSUP = Path('DataUnsupervised')
DATA_DF_UNSUP = pd.read_csv(DATA_DIR_UNSUP / 'coloc_gs_unsup.csv')

CROP_SZ = 128
FOLD = 5
N_FOLDS = 5

MODEL = pi_model
BATCH_SIZE = 16
VERBOSE = False
INIT_WEIGHTS = 'checkpoints/checkpoint.pi_model.sz128.fold5-5.05-0.05.hdf5'
MODEL_CHECKPOINT = f'checkpoints/checkpoint.{MODEL.__name__}.sz{CROP_SZ}.fold{FOLD}-{N_FOLDS}.{{epoch:02d}}-{{val_out1_loss:.2f}}.hdf5'
CSV_LOGGER = CSVLogger(f'logs/{MODEL.__name__}.sz{CROP_SZ}.log', append=True)

LR = 1e-4
OPTIMIZER = 'adam'
EPOCHS = 200
# LR_STEPS = {0: 1e-3, 10: 1e-4, 100: 5e-5}
LR_STEPS = {0: 5e-5}
scheduler = get_scheduler(LR_STEPS)

LOSS_WEIGHTS = (0.5, 10.0)   # supervised/unsupervised


def train(test_fold, n_folds):
    train_df, test_df = train_test_split(DATA_DF, test_fold=test_fold, n_folds=n_folds)
    model = MODEL(lr=LR, weights=INIT_WEIGHTS, optimizer=OPTIMIZER, loss_weights=LOSS_WEIGHTS)
    train_iterator = IteratorPi(sup_data_dir=DATA_DIR, unsup_data_dir=DATA_DIR_UNSUP,
                                sup_df=train_df, unsup_df=DATA_DF_UNSUP,
                                crop_sz=CROP_SZ, #augment=train_transform(),
                                target_noise=0.0,
                                shuffle=True, seed=None, infinite_loop=True, batch_size=BATCH_SIZE,
                                verbose=VERBOSE, gen_id='train', output_fname=False)
    val_iterator = IteratorPi(sup_data_dir=DATA_DIR, unsup_data_dir=DATA_DIR,
                              sup_df=test_df, unsup_df=test_df,
                              crop_sz=CROP_SZ, target_noise=0.0,
                              shuffle=False, seed=None, infinite_loop=False, batch_size=BATCH_SIZE,
                              verbose=VERBOSE, gen_id='val', output_fname=False)

    x, y, w = zip(*val_iterator)
    x = [np.concatenate(_x) for _x in zip(*x)]
    y = [np.concatenate(_y).flatten() for _y in zip(*y)]
    w = [np.concatenate(_w) for _w in zip(*w)]
    validation_data = x, y, w
    callbacks = [
        ModelCheckpoint(MODEL_CHECKPOINT, monitor='val_out1_loss',
                        save_best_only=True),
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
