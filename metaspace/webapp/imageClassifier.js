import * as _ from 'lodash';
import apolloClient from './src/graphqlClient';
import * as config from './src/clientConfig-coloc.json';
import {ICBlockAnnotationsQuery} from './src/modules/ImageClassifier/components/ICBlockAnnotation';
import {decode as decodePng} from 'fast-png';
import fetch from 'node-fetch';
import Prando from 'prando';

const csvStringifySync = require('csv-stringify/lib/sync');


const configureKnex = async () => {
  const knex = require('knex')({
    client: 'sqlite3',
    connection: {
      filename: './manualsort.sqlite',
    },
    useNullAsDefault: true,
  });

  if (!await knex.schema.hasTable('manualsort')) {
    await knex.schema.createTable('manualsort', (table) => {
      table.increments();
      // Important fields
      table.string('datasetId');
      table.string('user');
      table.integer('setIdx');
      table.float('pixelFillRatioThreshold');
      table.string('baseAnnotationId');
      table.string('otherAnnotationId');
      table.integer('rank');
      table.boolean('isIncomplete');
      // Additional info
      table.string('dsName');
      table.string('baseSf');
      table.string('baseAdduct');
      table.float('basePixelFillRatio');
      table.string('baseIonImageUrl');
      table.string('otherSf');
      table.string('otherAdduct');
      table.string('otherIonImageUrl');
      table.float('otherPixelFillRatio');
      table.integer('otherOriginalIdx');
      table.string('source');
      table.timestamp('created_at').defaultTo(knex.fn.now());
      table.timestamp('deleted_at');
    });
    await knex.schema.raw(
      `CREATE UNIQUE INDEX IF NOT EXISTS unique_idx 
      ON manualsort (datasetId, user, baseAnnotationId, otherAnnotationId)
      WHERE deleted_at IS NULL`
    );
  }
  if (!await knex.schema.hasTable('datasetCache')) {
    await knex.schema.createTable('datasetCache', (table) => {
      table.increments();
      // Important fields
      table.string('datasetId');
      table.string('filter');
      table.string('annotationIds');
      table.string('annotationSetPixels');
      table.string('annotationRawData');
      table.timestamp('created_at').defaultTo(knex.fn.now());
    });
  }

  return knex;
};

const pooledExecutePromises = async (promiseFuncs, maxActive=10) => {
  const remaining = Object.entries(promiseFuncs);
  const results = new Array(promiseFuncs.length);
  const deque = () => {
    const next = remaining.shift();
    if (next != null) {
      return next[1]().then(
        result => {
          results[next[0]] = result;
          return deque();
        },
        error => {
          results[next[0]] = error;
          console.error(error);
          return deque();
        },
      )
    } else {
      return null;
    }
  };
  const runners = [];
  for (let i = 0; i < maxActive; i++) {
    runners.push(deque());
  }
  await Promise.all(runners);
  return results;
};

const shuffle = (list, seed='seed') => {
  const rng = new Prando(seed);
  const result = [];
  const remaining = list.slice();
  while (remaining.length > 0) {
    result.push(remaining.splice(rng.nextInt(0, remaining.length - 1), 1)[0])
  }
  return result;
};

const getImage = async (url) => {
  if (!url) return null;
  const pngResponse = await fetch(url);
  if (pngResponse.status >= 300) {
    console.error(`${url}: ${pngResponse.statusText} ${pngResponse.status}`);
    return null;
  }
  const buffer = await pngResponse.arrayBuffer();

  return decodePng(buffer)
};

const getSetPixels = (image) => {
  if (image.colourType !== 4) throw new Error('Unknown colourType: ' + image.colourType);
  const numPixels = image.data.length / 2;
  let unset = 0;
  for (let i = 0; i < image.data.length; i += 2) {
    if (image.data[i] === 0 && image.data[i+1] !== 0) unset++;
  }
  return (numPixels - unset) / numPixels;
};

function encode(str) {
  let newStr = '';
  for(let i = 0; i < (str||'').length; i++) {
    if ('+ ,.@:;'.includes(str[i])) {
      newStr += str[i];
    } else {
      newStr += encodeURIComponent(str[i]);
    }
  }
  return newStr;
}

const qs = (obj) => '?' + Object.entries(obj).map(([key, val]) => `${encode(key)}=${encode(val)}`).join('&');

const configureImageClassifier = async (app) => {
  const knex = await configureKnex();

  const getDatasetData = async (datasetId, filter) => {
    const normalizedFilter = JSON.stringify(_.fromPairs(_.sortBy(Object.entries(filter), entry => entry[0])));
    let datasetData = await knex('datasetCache').where({datasetId, filter: normalizedFilter}).first();
    if (datasetData == null) {
      // Get annotations
      console.log(`getDatasetData(${datasetId}) getting annotations...`);
      let {data: {allAnnotations: annotations}} = await apolloClient.query({
        query: ICBlockAnnotationsQuery,
        variables: {
          filter,
          datasetFilter: { ids: datasetId },
        }
      });
      annotations = shuffle(_.cloneDeep(annotations));
      console.log(`getDatasetData(${datasetId}) getting images...`);
      await pooledExecutePromises(annotations.map(ann => async () => {
        const image = await getImage(config.imageStorage + ann.isotopeImages[0].url);
        ann.pixelFillRatio = getSetPixels(image);
      }));
      console.log(`getDatasetData(${datasetId}) found ${annotations.length} annotations, `
      + [0.1, 0.2].map(ratio => annotations.filter(a => a.pixelFillRatio < ratio).length + ' at ' + ratio.toFixed(2)).join(', '));
      // Construct annotationSetPixels in order so that shuffle is preserved
      const annotationSetPixels = _.fromPairs(annotations.map(ann => [ann.id, ann.pixelFillRatio || 0]));
      datasetData = {
        datasetId,
        filter: normalizedFilter,
        annotationIds: JSON.stringify(annotations.map(a => a.id)),
        annotationSetPixels: JSON.stringify(annotationSetPixels),
        annotationRawData: JSON.stringify(_.keyBy(annotations, 'id')),
      };
      await knex('datasetCache').insert(datasetData)
    }
    ['filter','annotationIds','annotationSetPixels','annotationRawData'].forEach(f =>
      datasetData[f] = datasetData[f] && JSON.parse(datasetData[f])
    );

    return datasetData;
  };

  app.get('/manualsortapi/annotations', async (req, res, next) => {
    try {
      const { datasetIds, filter, pix } = req.query;
      const pixelThreshold = parseFloat(pix) || 0;
      const data = await Promise.all(datasetIds
        .split(',')
        .map(datasetId => getDatasetData(datasetId, JSON.parse(filter || '{}')))
      );

      const selectedAnnotations = data.map(ds => {
        const annotations = Object.entries(ds.annotationSetPixels)
          .filter(([id, pixelRatio]) => pixelRatio >= pixelThreshold)
          .map(([id, pixelRatio]) => ds.annotationRawData[id]);
        return [ds.datasetId, annotations];
      });

      res.send(_.fromPairs(selectedAnnotations));
    } catch (err) { next(err) }
  });


  app.get('/manualsortapi/export', async (req, res, next) => {
    try {
      console.log('exporting');

      let rows = await knex('manualsort')
        .whereNull('deleted_at')
        .orderBy(['datasetId', 'user', 'baseAnnotationId', 'rank']);
      var host = 'http://' + req.headers.host;

      const completionStatus = _.groupBy(rows, r => ['datasetId','user','setIdx','pixelFillRatioThreshold','baseAnnotationId'].map(p => r[p]).join(','));
      Object.values(completionStatus).forEach(group => {
        let isIncomplete;
        if (group[0].isIncomplete != null && group[0].isIncomplete != '') {
          isIncomplete = !!group[0].isIncomplete;
        } else {
          isIncomplete = !group.every(row => row.rank != null);
        }
        group.forEach(row => {row.isIncomplete = String(isIncomplete)});
      });

      rows = rows.map(r => {
        const queryString = qs({user: r.user, pix: r.pixelFillRatioThreshold, sets: `${r.datasetId}:${r.setIdx}`});
        return {
          ..._.omit(r, ['deleted_at']),
          baseIonImageUrl: config.imageStorage + r.baseIonImageUrl,
          otherIonImageUrl: config.imageStorage + r.otherIonImageUrl,
          link: `${host}/manualsort${queryString}`,
        }
      });
      const csv = csvStringifySync(rows, {header: true});
      res.header('Content-Type', 'text/csv');
      res.header('Content-Disposition', 'inline; filename="results.csv"');
      res.send(csv);
      // await writeFileAtomic(path.resolve(__dirname, './static/results.csv'), csv);
      // console.log('done');

    } catch (err) {
      next(err);
    }
  });

  app.get('/manualsortapi', async (req, res, next) => {
    try {
      const { datasetId, user } = req.query;
      if (!datasetId || !user) {
        next();
      }
      const results = await knex('manualsort').where({ datasetId, user })
                                              .whereNull('deleted_at')
                                              .orderBy(['baseAnnotationId', 'rank']);
      const groupedResults = Object.values(_.groupBy(results, 'baseAnnotationId'));
      const structuredResults = groupedResults.map(grp => {
        return {
          ..._.pickBy(grp[0], (v, k) => !k.startsWith('other') && !['rank','id','created_at','deleted_at'].includes(k)),
          otherAnnotations: grp.map(item => {
            return _.pickBy(item, (v, k) => k.startsWith('other') || ['rank'].includes(k))
          })
        }
      });
      res.send(structuredResults);
    } catch (err) {
      next(err);
    }
  });

  app.post('/manualsortapi', async (req, res, next) => {
    try {
      const { datasetId, user, otherAnnotations, baseAnnotationId, ...baseAnn } = req.body;
      await knex.transaction(async trx => {
        await trx('manualsort')
          .whereNull('deleted_at')
          .where({ datasetId, user, baseAnnotationId })
          .update({ deleted_at: knex.fn.now() });
        await trx('manualsort')
          .insert(otherAnnotations
            .map((ann) => ({ ...ann, ...baseAnn, baseAnnotationId, datasetId, user })));
      });
      res.send();
    } catch (err) {
      next(err);
    }
  });
};


module.exports = {
  configureImageClassifier
};
