import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error as mse
from scipy.stats import spearmanr, kendalltau, pearsonr
import warnings


def accuracy(y1, y2, txt='', verbose=True):
    if verbose:
        if len(txt) > 0:
            print(txt)
        print(f'Spearmanr corr:\t{spearmanr(y1, y2)}\n'
              f'Kendalltau corr:\t{kendalltau(y1, y2)}\n'
              f'Pearsonr corr:\t{pearsonr(y1, y2)}\n'
              f'MSE:\t{mse(y1, y2)}\n')
    return spearmanr(y1, y2)


def conf_intervals(df, y_nm, y_pred_nm, fun, n=1000):
    def fun_(d):
        return fun(d[:, 0], d[:, 1])[0]

    data = np.column_stack((df[y_nm].values, df[y_pred_nm].values))
    sample = [fun_(data[np.random.choice(len(data), len(data), replace=True)]) for _ in range(n)]

    ci_lo = np.percentile(sample, 2.5)
    median = np.percentile(sample, 50)
    ci_hi = np.percentile(sample, 97.5)

    conf = f'median={median:0.3f}+{ci_hi - median:0.4f}-{median - ci_lo:0.4f}' \
        f'(95% confidence intervals: lo_ci={ci_lo:0.3f} / hi_ci={ci_hi:0.3f})'
    return conf


def conf_intervals2(df, y_nm, y_pred_nm, fun, n=100):
    sample = []
    for _ in range(n):
        sample_df = df.sample(len(df), replace=True)
        corrs = []
        for g in sample_df.groupby(['datasetId', 'baseSf', 'baseAdduct']):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                res = fun(g[1][y_nm], g[1][y_pred_nm])[0]
            if np.isnan(res):
                continue
            corrs.append(res)
        sample.append(np.array(corrs).mean())
    sample = np.array(sample)

    ci_lo = np.percentile(sample, 2.5)
    median = np.percentile(sample, 50)
    mean = np.mean(sample)
    ci_hi = np.percentile(sample, 97.5)

    conf = f'mean={mean:0.3f}|median={median:0.3f} ({ci_lo:0.3f}-{ci_hi:0.3f}) (95% CI)'
    return conf


def conf_intervals3(df, y_nm, y_pred_nm, fun, n=100):
    corrs = []
    for g in df.groupby(['datasetId', 'baseSf', 'baseAdduct']):
        res = fun(g[1][y_nm], g[1][y_pred_nm])[0]
        corrs.append(res)
    corrs = np.array(corrs)

    sample = np.array([corrs[np.random.choice(len(corrs), len(corrs), replace=True)].mean() for _ in range(n)])

    ci_lo = np.percentile(sample, 2.5)
    median = np.percentile(sample, 50)
    mean = np.mean(sample)
    ci_hi = np.percentile(sample, 97.5)

    conf = f'mean={mean:0.3f}|median={median:0.3f} ({ci_lo:0.3f}-{ci_hi:0.3f}) (95% CI)'
    return conf


def dataset_wise(df, cols, fun=spearmanr):
    acc = []
    for g in df.groupby(['datasetId', 'baseSf', 'baseAdduct']):
        acc.append(fun(g[1][cols[0]], g[1][cols[1]])[0])
    acc = np.array(acc)
    return acc.mean(), np.median(acc)


if __name__ == '__main__':
    df_preds = pd.read_csv('prediction/preds_mu.csv')
    df_preds['pred'] = df_preds['pred'].apply(lambda x: np.round(x))

    # add prediction rank
    for g in df_preds.groupby(['datasetId', 'baseSf', 'baseAdduct']):
        rank = g[1]['pred'].rank() - 1
        df_preds.loc[g[1].index, 'pred_rank'] = (rank - rank.min()) / (rank.max() - rank.min()) * 10

    accuracy(df_preds['rank'], df_preds['pred'], f'\nTotal preds {len(df_preds)}:')
    accuracy(df_preds['rank'], df_preds['pred_rank'], f'\nTotal preds ranked {len(df_preds)}:')

    mean, median = dataset_wise(df_preds, cols=['rank', 'pred'], fun=spearmanr)
    print(f'Spearman dataset-wise: mean {mean:0.3f}, median {median:0.3f}')
    # acc = dataset_wise(df_preds, cols=['rank', 'pred_rank'], fun=spearmanr)
    # print(f'Ranked spearman dataset-wise {acc}')

    # acc = dataset_wise(df_preds, cols=['rank', 'pred'], fun=pearsonr)
    # print(f'Pearson dataset-wise {acc}')
    # acc = dataset_wise(df_preds, cols=['rank', 'pred_rank'], fun=pearsonr)
    # print(f'Ranked pearson dataset-wise {acc}')

    mean, median = dataset_wise(df_preds, cols=['rank', 'pred'], fun=kendalltau)
    print(f'Kendalltau dataset-wise: mean {mean:0.3f}, median {median:0.3f}')
    # acc = dataset_wise(df_preds, cols=['rank', 'pred_rank'], fun=kendalltau)
    # print(f'Ranked kendalltau dataset-wise {acc}')

    # print()
    # print('Confidence intervals, whole data:')
    # print('Spearman:', conf_intervals(df_preds, 'rank', 'pred', spearmanr))
    # print('Kendalltau:', conf_intervals(df_preds, 'rank', 'pred', kendalltau))
    # print('Pearsonr:', conf_intervals(df_preds, 'rank', 'pred', pearsonr))

    # print()
    # print('Dataset-wise:')
    # print('Spearman:', conf_intervals2(df_preds, 'rank', 'pred', spearmanr))
    # print('Kendalltau:', conf_intervals2(df_preds, 'rank', 'pred', kendalltau))

    print()
    print('Dataset-wise 3:')
    print('Spearman:', conf_intervals3(df_preds, 'rank', 'pred', spearmanr))
    print('Kendalltau:', conf_intervals3(df_preds, 'rank', 'pred', kendalltau))
