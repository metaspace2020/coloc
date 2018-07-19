import apolloClient from '../../../graphqlClient';
import gql from 'graphql-tag';
import { forEach, fromPairs, get, groupBy, map, pick } from 'lodash-es';
import * as config from '../../../clientConfig.json';
import { AnnotationLabel, ICBlockAnnotation, ICBlockAnnotationsQuery } from './ICBlockAnnotation';

//              0   1       2      3        4          5
//              id  adduct  user   label    ds_name    formula
type DataRow = [string, string, string, string, string, string];

const process = async (item: AnnotationLabel) => {
  try {
    await fetch(`${config.imageClassifierUrl}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(item)
    });
  } catch(err) {
    console.error(err);
    console.info('Processing item: ', item);
  }
};

const runImport = async (data: DataRow[]) => {
  const allDss = await apolloClient.query<{allDatasets: {id: string, name: string}[] }>({
    query: gql`query{ allDatasets(limit: 10000) {id, name} }`
  });

  console.log(allDss.data);
  const nameMap = fromPairs(allDss.data.allDatasets.map(({id, name}) => ([name, id])));
  const byDsName = groupBy(data, '4');
  const missingDsIds: string[] = [];
  const byDsId: Record<string, AnnotationLabel[]> = {};

  forEach(byDsName, (rows, dsName) => {
    const datasetId = nameMap[dsName] as string | null;
    if (!datasetId) {
      missingDsIds.push(dsName);
    } else {
      byDsId[datasetId] = rows.map(([id, adduct, user, label, dsName, sumFormula]) => {
        const adductEnglish = adduct.replace('+','plus_').replace('-', 'minus_');
        const annotationId = [datasetId, 'HMDB-v4_2018-04-09', sumFormula, adductEnglish].join('_');
        const type = label === 'on' ? 1 : label === 'off' ? 2 : (label as any as number);
        return {
          // idx: id,
          datasetId, user, annotationId, type, dsName, sumFormula, adduct,
          source: 'import',
        };
      });
    }
  });

  (window as any).nameMap = nameMap;
  (window as any).byDsId = byDsId;

  if(missingDsIds.length) {
    console.warn('Skipping unrecognized datasets: ', missingDsIds);
  }

  for (const dsId in byDsId) {
    const labels = byDsId[dsId];

    console.log(`Importing ${dsId}`)
    const res = await apolloClient.query<{allAnnotations: ICBlockAnnotation[]}>({
      query: ICBlockAnnotationsQuery,
      variables: {
        filter: {},
        datasetFilter: {ids: dsId},
      },
    });

    const allRealAnnotationIds = map(res.data.allAnnotations, 'id');
    const foundLabels = labels.filter(({annotationId}) => allRealAnnotationIds.includes(annotationId));
    const missingLabels = labels.filter(label => !foundLabels.includes(label));
    console.log(`Matched ${foundLabels.length} out of ${labels.length}`, {missingLabels, foundLabels});
    const cleanedLabels: AnnotationLabel[] = foundLabels.map(label => {
      const {mz, msmScore, fdrLevel, isotopeImages} = res.data.allAnnotations.find(a => a.id === label.annotationId)!;
      return {
        ...label,
        mz, msmScore, fdrLevel,
        ionImageUrl: get(isotopeImages, [0, 'url']),
      };
    });

    await Promise.all(cleanedLabels.map(process));
    console.log('Done');
  }
};

(window as any).runImport = runImport;

// apolloClient.query({ query: gql`query{ molecularDatabases{id,name,version} }`}).then(console.log);
