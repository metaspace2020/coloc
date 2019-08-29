import umap
import pandas as pd
import numpy as np
import numba
from scipy import ndimage
from scipy.stats import spearmanr, kendalltau, pearsonr
import cv2
from pathlib import Path
from scipy.stats import spearmanr
from itertools import product, chain
import pickle


@numba.njit()
def spearmanr_dist(a, b):
    def _rankdata(x):
        temp = np.argsort(x)
        x_ranked = np.empty_like(x, dtype=np.float32)
        x_ranked[temp] = np.arange(len(x))
        return x_ranked

    a_ranked = _rankdata(a)
    b_ranked = _rankdata(b)
    ab = np.column_stack((a_ranked, b_ranked))
    rs = np.corrcoef(ab, rowvar=0)
    return 1 - rs[1, 0]


DATA_DIR = Path('Data')
EXT = 'tif'
DATA_DF = pd.read_csv(DATA_DIR / 'coloc_gs.csv')
PREDS_DF = 'prediction/preds_unsupervised.csv'
AUX_IMAGES = list(Path('DataUnsupervised').glob('*.tif'))[:0]

# U-map
MIN_DIST = 1.0
N_NEIGHBORS = 600
N_COMPONENTS = 20
CROP_SZ = 96

METRICS = ['correlation', 'cosine']
RANDOM_STATES = range(20)
UMAP_SETTINGS = product(METRICS, RANDOM_STATES)
naugs = len(RANDOM_STATES) * len(METRICS)
FEATURE_DICT = Path(f'Data/features.ncomp{N_COMPONENTS}.crop{CROP_SZ}.naugs{naugs}'
                    f'{".aux" if len(AUX_IMAGES) > 0 else ""}.pkl')


# def dist(a):
#     """calculate distances a[0]<->a[1:]"""
#     return np.sqrt(np.square(a[1:] - a[0]).sum(axis=1))
def dist(a):
    """calculate distances a[0]<->a[1:]"""
    return np.array([-pearsonr(a[0], x)[0] for x in a[1:]])


def preprocess(img, crop_sz):
    if crop_sz is None:
        return img
    else:
        return cv2.resize(img, dsize=(crop_sz, crop_sz), interpolation=cv2.INTER_CUBIC)


def rankdata(dist):
    temp = np.argsort(dist)
    pred_ranks = np.empty_like(temp, dtype=np.float32)
    pred_ranks[temp] = np.arange(len(dist))
    return pred_ranks


if __name__ == '__main__':
    image_paths = []
    for g in DATA_DF.groupby(['datasetId', 'baseSf']):
        new_group = True
        for _, row in g[1].iterrows():
            datasetId, baseSf, baseAdduct, otherSf, otherAdduct, rank = row
            base_ion = '.'.join((baseSf, baseAdduct.replace('+', 'p').replace('-', 'm')))
            other_ion = '.'.join((otherSf, otherAdduct.replace('+', 'p').replace('-', 'm')))
            base_img = DATA_DIR / '.'.join((datasetId, base_ion, EXT))
            other_img = DATA_DIR / '.'.join((datasetId, other_ion, EXT))
            if new_group:  # base_img always goes first
                image_paths.append(base_img)
                new_group = False
            image_paths.append(other_img)

    image_list = [cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE) for img_path in image_paths + AUX_IMAGES]
    image_list = [preprocess(img, CROP_SZ) for img in image_list]
    # image_list = [np.load(img_path) for img_path in image_paths]
    # image_list = [ndimage.zoom(img, (CROP_SZ / img.shape[0], CROP_SZ / img.shape[1])) for img in image_list + AUX_IMAGES]

    data = np.stack([d.flatten() for d in image_list])

    embedding_stated = []
    for i, setting in enumerate(UMAP_SETTINGS):
        metric, rs = setting
        print(f'U-Map: metric \'{metric}\', random state {rs}, {i + 1}/{naugs}')
        embd = umap.UMAP(metric=metric, n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST,
                         n_components=N_COMPONENTS, random_state=rs).fit_transform(data)
        embedding_stated.append(embd)

    feature_dict = dict(zip(map(str, image_paths), np.concatenate(embedding_stated, axis=-1)))
    print('Dumping features to', FEATURE_DICT)
    with open(FEATURE_DICT, 'wb') as f:
        pickle.dump(feature_dict, f)

    mean_acc = []
    pred_ranks_all = []
    ranks_all = []
    i = 0
    for g in DATA_DF.groupby(['datasetId', 'baseSf']):
        pred_ranks = []
        pred_distances = []
        for embedding in embedding_stated:
            group_embedding = embedding[i: i + len(g[1]) + 1]
            distances = dist(group_embedding)
            pred_ranks.append(rankdata(distances))
            pred_distances.append(distances)

        i += len(g[1]) + 1
        pred_ranks = np.stack(pred_ranks, axis=-1)
        pred_ranks = np.mean(pred_ranks, axis=-1)

        # pred_distances = np.stack(pred_distances, axis=-1)
        # pred_distances = np.mean(pred_distances, axis=-1)
        # pred_ranks = rankdata(pred_distances)

        DATA_DF.loc[g[1].index, 'pred'] = pred_ranks
        acc = spearmanr(g[1]['rank'], pred_ranks).correlation
        mean_acc.append(acc)
        print(f'{g[0]}: Spearman {acc}')

        ranks_all.append(g[1]['rank'].values)
        pred_ranks_all.append(pred_ranks)

    DATA_DF.to_csv(PREDS_DF, index=False)

    mean_acc = np.array(mean_acc).mean()
    print(f'\nMean corr {mean_acc}')

    ranks_all = np.concatenate(ranks_all)
    pred_ranks_all = np.concatenate(pred_ranks_all)
    mean_acc_all = spearmanr(ranks_all, pred_ranks_all).correlation
    print(f'\nMean corr global {mean_acc_all}')
