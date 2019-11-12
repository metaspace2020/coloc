import cv2
import numpy as np
from pathlib import Path
import pandas as pd
import re
import threading
from keras import backend as K
from albumentations import (
    HorizontalFlip,
    VerticalFlip,
    Compose,
    RandomRotate90,
    GridDistortion,
    ElasticTransform,
    OpticalDistortion,
    HueSaturationValue,
    RandomGamma,
    ShiftScaleRotate,
    BasicTransform,
)


def preprocess(x):
    return x / 255. * 2. - 1.0


def reprocess(x):
    return ((x + 1) / 2 * 255).astype(np.uint8)


class FlipChannels(BasicTransform):
    def apply(self, img, **params):
        channels = np.arange(img.shape[-1])
        np.random.RandomState(seed=None).shuffle(channels)
        img = img[..., channels]
        return img

    @property
    def targets(self):
        return {'image': self.apply}

    def get_transform_init_args_names(self):
        return ()

    def get_params_dependent_on_targets(self, params):
        return ()


def contrast_norm(fun):
    def wrapper(img):
        img_norm = np.stack([cv2.equalizeHist(img[..., 0]), cv2.equalizeHist(img[..., 1])], axis=-1)
        return fun(img_norm)
    return wrapper


# @contrast_norm
def null_transform(img):
    return img


def train_transform(p=1.0):
    augmentation = Compose([
        FlipChannels(),
        VerticalFlip(p=p),
        HorizontalFlip(p=p),
        RandomRotate90(p=p),

        RandomGamma(p=p, gamma_limit=(90, 350)),
        OpticalDistortion(p=p, border_mode=cv2.BORDER_CONSTANT),
        GridDistortion(p=p, border_mode=cv2.BORDER_CONSTANT),
        ShiftScaleRotate(p=p, scale_limit=0.2, border_mode=cv2.BORDER_CONSTANT)
    ], p=p)

    # @contrast_norm
    def transform_fun(img):
        data = {'image': img}
        augmented = augmentation(**data)
        return augmented['image']

    return transform_fun


class Iterator(object):
    """Iterator for co-localization"""

    def __init__(self, data_dir, data_df, crop_sz, augment=null_transform, target_noise=0.0,
                 shuffle=True, seed=None, infinite_loop=True, batch_size=32,
                 verbose=False, gen_id='', output_fname=False):
        self.lock = threading.Lock()
        self.data_dir = data_dir
        self.data_df = data_df
        self.crop_sz = crop_sz
        self.shuffle = shuffle
        self.seed = seed
        self.verbose = verbose
        self.gen_id = gen_id
        self.batch_index = 0    # Ensure self.batch_index is 0.
        self.total_batches_seen = 0
        self.infinite_loop = infinite_loop
        self.batch_size = batch_size
        self.index_generator = self._flow_index()
        self.n_channels = 2     # we compare 2 images
        self.output_fname = output_fname
        self.augment = augment
        self.target_noise = target_noise

    def _flow_index(self):
        data_len = len(self.data_df)
        while 1:
            if self.seed is None:
                random_seed = None
            else:
                random_seed = self.seed + self.total_batches_seen

            # next epoch
            if self.batch_index == 0:
                if not self.infinite_loop and (self.total_batches_seen > 0):
                    break
                if self.verbose:
                    print(f'\n************** New epoch. Generator {self.gen_id} *******************')
                if self.shuffle:
                    self.data_df = self.data_df.sample(data_len, random_state=random_seed)

            current_index = self.batch_index * self.batch_size
            if data_len > current_index + self.batch_size:
                current_batch_size = self.batch_size
                self.batch_index += 1
            else:
                current_batch_size = data_len - current_index
                self.batch_index = 0
            self.total_batches_seen += 1

            yield self.data_df.iloc[current_index: current_index + current_batch_size], \
                  current_index, current_batch_size

    def next(self):
        with self.lock:
            df_slice, current_index, current_batch_size = next(self.index_generator)

        batch_x = np.zeros((current_batch_size, self.crop_sz, self.crop_sz, self.n_channels), dtype=K.floatx())
        batch_y = np.zeros((current_batch_size, 1), dtype=K.floatx())
        batch_fname = []

        for i, (df_index, row) in enumerate(df_slice.iterrows()):
            datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row
            base_ion = '.'.join((baseSf, baseAdduct.replace('+', 'p').replace('-', 'm')))
            other_ion = '.'.join((otherSf, otherAdduct.replace('+', 'p').replace('-', 'm')))
            first_img = str(self.data_dir / '.'.join((datasetId, base_ion, 'tif')))
            other_img = str(self.data_dir / '.'.join((datasetId, other_ion, 'tif')))
            img = np.stack([cv2.imread(first_img, cv2.IMREAD_GRAYSCALE),
                            cv2.imread(other_img, cv2.IMREAD_GRAYSCALE)],
                            axis=-1)
            img = cv2.resize(img, dsize=(self.crop_sz, self.crop_sz), interpolation=cv2.INTER_CUBIC)
            img = self.augment(img)
            batch_x[i] = img
            batch_y[i] = np.clip(rank + np.random.uniform(-self.target_noise, self.target_noise) * 10, 0, 10) / 10
            batch_fname.append((datasetId, base_ion, other_ion))

        batch_x = preprocess(batch_x)

        if K.image_data_format() == 'channels_first':   # theano format
            batch_x = np.moveaxis(batch_x, -1, 1)

        result = batch_x, batch_y
        if self.output_fname:
            result += (batch_fname,)
        return result

    def __iter__(self):
        # Needed if we want to do something like:
        # for x, y in data_gen.flow(...):
        return self

    def __next__(self, *args, **kwargs):
        return self.next(*args, **kwargs)


class IteratorPi(object):
    """Iterator for co-localization Pi-models"""

    # Samples supervised and unsupervised lists 1:1
    def __init__(self, sup_data_dir, unsup_data_dir, sup_df, unsup_df, crop_sz,
                 augment=null_transform, target_noise=0.0,
                 shuffle=True, seed=None, infinite_loop=True, batch_size=32,
                 verbose=False, gen_id='', output_fname=False):
        self.lock = threading.Lock()
        self.sup_data_dir = sup_data_dir
        self.unsup_data_dir = unsup_data_dir
        self.sup_df = sup_df
        self.unsup_df = unsup_df
        self.crop_sz = crop_sz
        self.shuffle = shuffle
        self.seed = seed
        self.verbose = verbose
        self.gen_id = gen_id
        self.batch_index = 0    # Ensure self.batch_index is 0.
        self.total_batches_seen = 0
        self.infinite_loop = infinite_loop
        self.sup_batch_size = int(np.ceil(batch_size / 2.0))
        self.unsup_batch_size = batch_size - self.sup_batch_size
        self.index_generator = self._flow_index()
        self.n_channels = 2     # we compare 2 images
        self.output_fname = output_fname
        self.augment = augment
        self.target_noise = target_noise

    def _flow_index(self):
        data_len = len(self.sup_df)
        while 1:
            if self.seed is None:
                random_seed = None
            else:
                random_seed = self.seed + self.total_batches_seen

            # next epoch
            if self.batch_index == 0:
                if not self.infinite_loop and (self.total_batches_seen > 0):
                    break
                if self.verbose:
                    print(f'\n************** New epoch. Generator {self.gen_id} *******************')
                if self.shuffle:
                    self.sup_df = self.sup_df.sample(data_len, random_state=random_seed)

            current_index = self.batch_index * self.sup_batch_size
            if data_len > current_index + self.sup_batch_size:
                current_sup_batch_size = self.sup_batch_size
                self.batch_index += 1
            else:
                current_sup_batch_size = data_len - current_index
                self.batch_index = 0
            self.total_batches_seen += 1

            yield self.sup_df.iloc[current_index: current_index + current_sup_batch_size], \
                  self.unsup_df.sample(self.unsup_batch_size), \
                  current_sup_batch_size, self.unsup_batch_size

    def next(self):
        with self.lock:
            sup_df_slice, unsup_df_slice, current_sup_batch_size, current_unsup_batch_size = next(self.index_generator)
        current_batch_size = current_sup_batch_size + current_unsup_batch_size
        input1 = np.zeros((current_batch_size, self.crop_sz, self.crop_sz, self.n_channels), dtype=K.floatx())
        input2 = np.zeros((current_batch_size, self.crop_sz, self.crop_sz, self.n_channels), dtype=K.floatx())
        output1 = np.zeros((current_batch_size, 1), dtype=K.floatx())
        output2 = np.zeros((current_batch_size, 1), dtype=K.floatx())
        batch_fname = []

        sample_weight1 = np.concatenate([np.ones(current_sup_batch_size, dtype=K.floatx()),
                                         np.zeros(current_unsup_batch_size, dtype=K.floatx())])
        sample_weight2 = np.ones(current_batch_size, dtype=K.floatx())

        for i, (df_index, row) in enumerate(sup_df_slice.iterrows()):
            datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row
            img, base_ion, other_ion = self._make_img(self.sup_data_dir, datasetId,
                                                      baseSf, baseAdduct, otherSf, otherAdduct)

            img_aug = self.augment(img)
            input1[i] = img_aug
            output1[i] = np.clip(rank + np.random.uniform(-self.target_noise, self.target_noise) * 10, 0, 10) / 10

            img_aug = self.augment(img)
            input2[i] = img_aug
            output2[i] = 0

            batch_fname.append((datasetId, base_ion, other_ion))

        for i, (df_index, row) in enumerate(unsup_df_slice.iterrows()):
            datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row
            img, base_ion, other_ion = self._make_img(self.unsup_data_dir, datasetId,
                                                      baseSf, baseAdduct, otherSf, otherAdduct)
            img_aug = self.augment(img)
            input1[i + current_sup_batch_size] = img_aug
            output1[i + current_sup_batch_size] = -100

            img_aug = self.augment(img)
            input2[i + current_sup_batch_size] = img_aug
            output2[i + current_sup_batch_size] = 0

            batch_fname.append((datasetId, base_ion, other_ion))

        input1 = preprocess(input1)
        input2 = preprocess(input2)

        if K.image_data_format() == 'channels_first':   # theano format
            input1 = np.moveaxis(input1, -1, 1)
            input2 = np.moveaxis(input2, -1, 1)

        result = [input1, input2], [output1, output2], [sample_weight1, sample_weight2]
        if self.output_fname:
            result += (batch_fname,)
        return result

    def _make_img(self, dir, datasetId, baseSf, baseAdduct, otherSf, otherAdduct):
        base_ion = '.'.join((baseSf, baseAdduct.replace('+', 'p').replace('-', 'm')))
        other_ion = '.'.join((otherSf, otherAdduct.replace('+', 'p').replace('-', 'm')))
        first_img = str(dir / '.'.join((datasetId, base_ion, 'tif')))
        other_img = str(dir / '.'.join((datasetId, other_ion, 'tif')))
        img = np.stack([cv2.imread(first_img, cv2.IMREAD_GRAYSCALE),
                        cv2.imread(other_img, cv2.IMREAD_GRAYSCALE)],
                       axis=-1)
        img = cv2.resize(img, dsize=(self.crop_sz, self.crop_sz), interpolation=cv2.INTER_CUBIC)
        return img, base_ion, other_ion

    def __iter__(self):
        # Needed if we want to do something like:
        # for x, y in data_gen.flow(...):
        return self

    def __next__(self, *args, **kwargs):
        return self.next(*args, **kwargs)


class IteratorMu(object):
    """Iterator for co-localization Mu-models"""

    # Samples supervised and unsupervised lists 1:1
    def __init__(self, data_dir, df, crop_sz,
                 augment=null_transform, validation_mode=False,
                 shuffle=True, seed=None, infinite_loop=True, batch_size=32,
                 verbose=False, gen_id='', output_fname=False):
        self.lock = threading.Lock()
        self.data_dir = data_dir
        self.df = df
        if not validation_mode:
            df['dataset'] = df['files'].apply(lambda f: f.split('.')[0])
            self.dataset_dict = {g[0]: list(g[1]['files']) for g in df.groupby('dataset')}
            self.dataset_dict = {k: v for k, v in self.dataset_dict.items() if len(v) > 1}
            self.dataset_list = list(self.dataset_dict)
        self.crop_sz = crop_sz
        self.shuffle = shuffle
        self.seed = seed
        self.verbose = verbose
        self.gen_id = gen_id
        self.batch_index = 0    # Ensure self.batch_index is 0.
        self.total_batches_seen = 0
        self.infinite_loop = infinite_loop
        self.batch_size = batch_size
        self.output_fname = output_fname
        self.augment = augment
        self.validation_mode = validation_mode
        if validation_mode:
            self.index_generator = self._flow_index_val()
        else:
            self.index_generator = self._flow_index()

    def _flow_index(self):
        data_len = len(self.dataset_list)
        while 1:
            if self.seed is None:
                random_seed = None
            else:
                random_seed = self.seed + self.total_batches_seen

            # next epoch
            if self.batch_index == 0:
                if not self.infinite_loop and (self.total_batches_seen > 0):
                    break
                if self.verbose:
                    print(f'\n************** New epoch. Generator {self.gen_id} *******************')
                if self.shuffle:
                    np.random.RandomState(random_seed).shuffle(self.dataset_list)

            current_index = self.batch_index * self.batch_size
            if data_len > current_index + self.batch_size:
                current_batch_size = self.batch_size
                self.batch_index += 1
            else:
                current_batch_size = data_len - current_index
                self.batch_index = 0
            self.total_batches_seen += 1

            images = []
            for dataset in self.dataset_list[current_index: current_index + current_batch_size]:
                if self.shuffle:
                    np.random.RandomState(random_seed).shuffle(self.dataset_dict[dataset])
                images.append(self.dataset_dict[dataset][:2] + [None])

            yield images, current_batch_size

    def _flow_index_val(self):
        data_len = len(self.df)
        while 1:
            # next epoch
            if (self.batch_index == 0) and (self.total_batches_seen > 0):
                    break
            current_index = self.batch_index * self.batch_size
            if data_len > current_index + self.batch_size:
                current_batch_size = self.batch_size
                self.batch_index += 1
            else:
                current_batch_size = data_len - current_index
                self.batch_index = 0
            self.total_batches_seen += 1

            images = []
            for _, row in self.df.iloc[current_index: current_index + current_batch_size].iterrows():
                datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row.values
                base_ion = '.'.join((baseSf, baseAdduct.replace('+', 'p').replace('-', 'm')))
                other_ion = '.'.join((otherSf, otherAdduct.replace('+', 'p').replace('-', 'm')))
                first_img = '.'.join((datasetId, base_ion, 'tif'))
                other_img = '.'.join((datasetId, other_ion, 'tif'))
                images.append([first_img, other_img, rank])

            yield images, current_batch_size

    def next(self):
        with self.lock:
            images, current_batch_size = next(self.index_generator)
        input1 = np.zeros((current_batch_size, self.crop_sz, self.crop_sz, 1), dtype=K.floatx())
        input2 = np.zeros((current_batch_size, self.crop_sz, self.crop_sz, 1), dtype=K.floatx())
        output = np.zeros((current_batch_size, 1), dtype=K.floatx())
        batch_fname = []

        for i, (im1, im2, rank) in enumerate(images):
            img1 = self._make_img(self.data_dir / im1)
            img2 = self._make_img(self.data_dir / im2)

            if self.validation_mode:
                target = rank / 10
            else:
                # target = np.random.uniform(0, 1)
                max_categories = 2
                target = np.random.randint(max_categories) / (max_categories - 1)
                img2 = cv2.addWeighted(img1, (1 - target), img2, target, 0)

            img_aug = self.augment(np.stack([img1, img2], axis=-1))
            input1[i] = img_aug[..., [0]]
            input2[i] = img_aug[..., [1]]
            output[i] = target

            parse = re.match('([^.]+).(.+).tif', im1)
            datasetId = parse[1]
            base_ion = parse[2]
            parse = re.match('([^.]+).(.+).tif', im2)
            other_ion = parse[2]
            batch_fname.append((datasetId, base_ion, other_ion))

        input1 = preprocess(input1)
        input2 = preprocess(input2)

        if K.image_data_format() == 'channels_first':   # theano format
            input1 = np.moveaxis(input1, -1, 1)
            input2 = np.moveaxis(input2, -1, 1)

        result = [input1, input2], output
        if self.output_fname:
            result += (batch_fname,)
        return result

    def _make_img(self, image_path):
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img, dsize=(self.crop_sz, self.crop_sz), interpolation=cv2.INTER_CUBIC)
        return img

    def __iter__(self):
        # Needed if we want to do something like:
        # for x, y in data_gen.flow(...):
        return self

    def __next__(self, *args, **kwargs):
        return self.next(*args, **kwargs)


if __name__ == '__main__':
    from itertools import islice

    data_dir = Path('Data')
    files = list(data_dir.glob('*.tif'))
    data_df = pd.DataFrame(list(map(lambda f: f.parts[-1], files)), columns=['files'])
    # data_df = pd.read_csv('Data/coloc_gs_.csv')
    crop_sz = 256
    batch_iterator = IteratorMu(data_dir=data_dir, df=data_df, validation_mode=False,
                                crop_sz=crop_sz, augment=train_transform(),
                                shuffle=True, seed=None, infinite_loop=False, batch_size=5,
                                verbose=True, gen_id='1', output_fname=True)
    x, y, fname = zip(*islice(batch_iterator, 3))
    x = [reprocess(np.concatenate(_x)) for _x in zip(*x)]
    y = np.concatenate(y).flatten()
    fname = np.concatenate(fname)

    for x1, x2, y_, fname_ in zip(*x, y, fname):
        title = f'{fname_[0]}: {fname_[1]}, {fname_[2]}, target {y_}'
        cv2.imshow(title, np.hstack([x1, np.zeros((x1.shape[0], 2, 1), dtype=np.uint8), x2]))
        cv2.waitKey(0)
