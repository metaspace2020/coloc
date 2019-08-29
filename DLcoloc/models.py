from keras.models import Model
from keras.layers import Dense, Input
from keras.layers import Convolution2D, GlobalAveragePooling2D
from keras.layers import Average, Subtract, Concatenate, Lambda
from keras import backend as K
from keras.losses import mean_squared_error
from keras.optimizers import Adam, SGD
from keras.applications.xception import Xception

try:
    import h5py
except ImportError:
    h5py = None
import numpy as np
from keras.callbacks import Callback
import warnings


class ModelCheckpoint(Callback):
    """Save the model after every epoch.

    `filepath` can contain named formatting options,
    which will be filled the value of `epoch` and
    keys in `logs` (passed in `on_epoch_end`).

    For example: if `filepath` is `weights.{epoch:02d}-{val_loss:.2f}.hdf5`,
    then the model checkpoints will be saved with the epoch number and
    the validation loss in the filename.

    # Arguments
        filepath: string, path to save the model file.
        monitor: quantity to monitor.
        verbose: verbosity mode, 0 or 1.
        save_best_only: if `save_best_only=True`,
            the latest best model according to
            the quantity monitored will not be overwritten.
        mode: one of {auto, min, max}.
            If `save_best_only=True`, the decision
            to overwrite the current save file is made
            based on either the maximization or the
            minimization of the monitored quantity. For `val_acc`,
            this should be `max`, for `val_loss` this should
            be `min`, etc. In `auto` mode, the direction is
            automatically inferred from the name of the monitored quantity.
        save_weights_only: if True, then only the model's weights will be
            saved (`model.save_weights(filepath)`), else the full model
            is saved (`model.save(filepath)`).
        period: Interval (number of epochs) between checkpoints.
    """

    def __init__(self, filepath, monitor='val_loss', verbose=0,
                 save_best_only=False, save_weights_only=False,
                 mode='auto', period=1, layer_to_save='xception'):
        super(ModelCheckpoint, self).__init__()
        self.monitor = monitor
        self.verbose = verbose
        self.filepath = filepath
        self.save_best_only = save_best_only
        self.save_weights_only = save_weights_only
        self.period = period
        self.epochs_since_last_save = 0
        self.layer_to_save = layer_to_save

        if mode not in ['auto', 'min', 'max']:
            warnings.warn('ModelCheckpoint mode %s is unknown, '
                          'fallback to auto mode.' % (mode),
                          RuntimeWarning)
            mode = 'auto'

        if mode == 'min':
            self.monitor_op = np.less
            self.best = np.Inf
        elif mode == 'max':
            self.monitor_op = np.greater
            self.best = -np.Inf
        else:
            if 'acc' in self.monitor or self.monitor.startswith('fmeasure'):
                self.monitor_op = np.greater
                self.best = -np.Inf
            else:
                self.monitor_op = np.less
                self.best = np.Inf

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        self.epochs_since_last_save += 1
        if self.epochs_since_last_save >= self.period:
            self.epochs_since_last_save = 0
            filepath = self.filepath.format(epoch=epoch + 1, **logs)
            if self.save_best_only:
                current = logs.get(self.monitor)
                if current is None:
                    warnings.warn('Can save best model only with %s available, '
                                  'skipping.' % (self.monitor), RuntimeWarning)
                else:
                    if self.monitor_op(current, self.best):
                        if self.verbose > 0:
                            print('\nEpoch %05d: %s improved from %0.5f to %0.5f,'
                                  ' saving model to %s'
                                  % (epoch + 1, self.monitor, self.best,
                                     current, filepath))
                        self.best = current
                        if self.save_weights_only:
                            self.model.get_layer(self.layer_to_save).save_weights(filepath, overwrite=True)
                        else:
                            self.model.get_layer(self.layer_to_save).save(filepath, overwrite=True)
                    else:
                        if self.verbose > 0:
                            print('\nEpoch %05d: %s did not improve from %0.5f' %
                                  (epoch + 1, self.monitor, self.best))
            else:
                if self.verbose > 0:
                    print('\nEpoch %05d: saving model to %s' % (epoch + 1, filepath))
                if self.save_weights_only:
                    self.model.get_layer(self.layer_to_save).save_weights(filepath, overwrite=True)
                else:
                    self.model.get_layer(self.layer_to_save).save(filepath, overwrite=True)


def correlation(a):
    x, y = a
    mx = K.mean(x, axis=1, keepdims=True)
    my = K.mean(y, axis=1, keepdims=True)
    xm, ym = x - mx, y - my
    r_num = K.sum(xm * ym, axis=1, keepdims=True)
    r_den = K.sqrt(K.epsilon() + K.sum(K.square(xm), axis=1, keepdims=True) * K.sum(K.square(ym), axis=1, keepdims=True))
    r = r_num / r_den
    r = K.clip(r, -1.0, 1.0)
    return r


def correlation_loss(a):
    return 1 - correlation(a)


def xception(input_channels=2, lr=1e-4, weights=None, optimizer='adam'):

    if K.image_data_format() == 'channels_last':
        input_shape = (None, None, input_channels)
        input_shape_xception = (None, None, 3)
    else:
        input_shape = (input_channels, None, None)
        input_shape_xception = (3, None, None)

    xception_model = Xception(input_shape=input_shape_xception, include_top=False, weights='imagenet')

    main_input = Input(input_shape)
    x = Convolution2D(3, (1, 1), kernel_initializer='he_normal')(main_input)
    x = xception_model(x)
    x = GlobalAveragePooling2D(name='pool1')(x)
    output_activation = 'linear'
    main_output = Dense(1, activation=output_activation, name='predictions')(x)

    model = Model(main_input, main_output, name='xception')

    if weights is not None:
        print('Load weights from', weights)
        model.load_weights(weights)

    if optimizer.lower() == 'adam':
        optimizer = Adam(lr, decay=0.0005)
        print('Optimizer is Adam')
    elif optimizer.lower() == 'sgd':
        optimizer = SGD(lr, momentum=0.95, decay=0.0005, nesterov=True)
        print('Optimizer is SGD')
    else:
        raise ValueError('Unknown optimizer')

    model.compile(loss='mse', optimizer=optimizer, metrics=['mse'])

    return model


def pi_model(input_channels=2, lr=1e-4, weights=None, optimizer='adam', loss_weights=(0.5, 0.5)):
    """ Pi-model. https://arxiv.org/pdf/1610.02242.pdf """

    if K.image_data_format() == 'channels_last':
        input_shape = (None, None, input_channels)
    else:
        input_shape = (input_channels, None, None)

    core_model = xception(input_channels=input_channels, lr=lr, optimizer=optimizer,
                          weights=weights)
    input1 = Input(input_shape)
    input2 = Input(input_shape)
    x1 = core_model(input1)
    x2 = core_model(input2)
    out1 = Average(name='out1')([x1, x2])
    out2 = Subtract(name='out2')([x1, x2])

    model = Model(inputs=[input1, input2], outputs=[out1, out2], name='pi_model')
    model.compile(optimizer=optimizer,
                  loss={'out1': 'mse', 'out2': 'mse'},
                  loss_weights={'out1': loss_weights[0], 'out2': loss_weights[1]})
    return model


def mu_model(lr=1e-4, weights=None, optimizer='adam', embd_dim=128, return_core_model=False):

    def euclidean_distance(vects):
        x, y = vects
        sum_square = K.sum(K.square(x - y), axis=1, keepdims=True)
        return K.sqrt(K.maximum(sum_square, K.epsilon()))

    def correlation_distance(vects):
        # d = -K.elu(1.4*(correlation(vects) - 1))
        d = 1 - correlation(vects)
        return d

    def dist_output_shape(shapes):
        shape1, shape2 = shapes
        return (shape1[0], 1)

    if K.image_data_format() == 'channels_last':
        input_shape = (None, None, 2)
        input_core_shape = (None, None, 1)
        input_shape_xception = (None, None, 3)
    else:
        input_shape = (2, None, None)
        input_core_shape = (1, None, None)
        input_shape_xception = (3, None, None)

    def create_core_model(input_shape, weights):
        xception_model = Xception(input_shape=input_shape_xception, include_top=False, weights='imagenet')
        input = Input(shape=input_shape)
        x = Convolution2D(3, (1, 1), kernel_initializer='he_normal')(input)
        x = xception_model(x)
        x = GlobalAveragePooling2D(name='pool')(x)
        output = Dense(embd_dim, activation='elu', kernel_initializer='he_normal', name='embd')(x)
        model = Model(input, output, name='core_model')
        if weights is not None:
            print('Load weights from', weights)
            model.load_weights(weights)
        return model

    core_model = create_core_model(input_core_shape, weights)
    if return_core_model:
        return core_model

    input = Input(input_shape)
    if K.image_data_format() == 'channels_last':
        input1 = Lambda(lambda x: x[..., 0: 1])(input)
        input2 = Lambda(lambda x: x[..., 1: 2])(input)
    else:
        input1 = Lambda(lambda x: x[0: 1])(input)
        input2 = Lambda(lambda x: x[0: 1])(input)
    x1 = core_model(input1)
    x2 = core_model(input2)
    output = Lambda(correlation_distance, output_shape=dist_output_shape, name='correlation')([x1, x2])

    model = Model(input, output, name='mu_model')

    if optimizer.lower() == 'adam':
        optimizer = Adam(lr, decay=0.0005)
        print('Optimizer is Adam')
    elif optimizer.lower() == 'sgd':
        optimizer = SGD(lr, momentum=0.95, decay=0.0005, nesterov=True)
        print('Optimizer is SGD')
    else:
        raise ValueError('Unknown optimizer')

    model.compile(loss='mse', optimizer=optimizer, metrics=['mse'])

    return model


if __name__ == '__main__':
    model = xception()
