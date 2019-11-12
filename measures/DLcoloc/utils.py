import pandas as pd
import numpy as np


def train_test_split(df, test_fold=5, n_folds=5):
    assert 1 <= test_fold <= n_folds
    datasets = sorted(df.groupby('datasetId').groups)
    datasets_count = len(datasets)
    fold_length = int(np.ceil(datasets_count / n_folds))
    test_index = range(fold_length * (test_fold - 1), min(datasets_count, fold_length * test_fold))
    train_index = [i for i in range(datasets_count) if i not in test_index]
    test_datasets = [datasets[i] for i in test_index]
    train_datasets = [datasets[i] for i in train_index]
    train_df = df.loc[df['datasetId'].isin(train_datasets)]
    test_df = df.loc[df['datasetId'].isin(test_datasets)]
    assert len(train_df) + len(test_df) == len(df)
    assert len(pd.merge(train_df, test_df, on='datasetId', how='inner')) == 0
    return train_df, test_df


if __name__ == '__main__':
    data_df = pd.read_csv('Data/coloc_gs.csv')
    for test_fold in range(1, 6):
        train_df, test_df = train_test_split(data_df, test_fold=test_fold, n_folds=5)
        print(len(test_df))

