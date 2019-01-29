import apolloClient from './src/graphqlClient';
import gql from 'graphql-tag';
import Prando from 'prando';
import _ from 'lodash';
const {mapValues, keyBy} = require('lodash');


const configureKnex = async () => {
  const knex = require('knex')({
    client: 'sqlite3',
    connection: {
      filename: './manualsort.sqlite',
    },
    useNullAsDefault: true,
  });

  if (!await knex.schema.hasTable('dataset')) {
    await knex.schema.createTable('dataset', (table) => {
      table.increments();
      table.string('datasetId');
      table.string('seed');
      table.string('baseAnnotationId');
      table.string('otherAnnotationIds');
      table.unique(['datasetId','seed']);
    });
  }

  if (!await knex.schema.hasTable('manualsort')) {
    await knex.schema.createTable('manualsort', (table) => {
      table.increments();
      // Important fields
      table.string('datasetId');
      table.string('user');
      table.string('baseAnnotationId');
      table.string('otherAnnotationId');
      table.integer('order');
      table.unique(['datasetId','user','baseAnnotationId','otherAnnotationId']);
      // Additional info
      table.string('dsName');
      table.string('baseSfAdduct');
      table.string('otherSfAdduct');
      table.string('baseIonImageUrl');
      table.string('otherIonImageUrl');
      table.string('source');
    });
  }

  return knex;
};

const NUM_PER_SET = 10;

const getAnnotationIdsForDataset = async (dsId, sets) => {
  const ds = await apolloClient.query({
    query: gql`{
      allAnnotations(datasetFilter: {ids: $id}, limit: 10000) {
        id
      }
    }`,
    variables: {id: dsId},
  });
  const annotationIds = ds.data.allAnnotations.map(a => a.id).sort();
  const randomizedAnnotationIds = [];
  const p = new Prando('seed');
  while(annotationIds.length > 0) {
    randomizedAnnotationIds.push(annotationIds.splice(p.nextInt(annotationIds.length), 1)[0]);
  }
  return _.flatMap(sets, setId => randomizedAnnotationIds.slice(setId * NUM_PER_SET, (setId + 1) * NUM_PER_SET));
};

const configureImageClassifier = async (app) => {
  const knex = await configureKnex();

  app.get('/manualsortapi', async (req, res, next) => {
    try {
      const { datasetId, user, raw } = req.query;
      if (!datasetId || !user) {
        next();
      }
      if (raw) {
        const results = await knex('imageclassifications').where({ datasetId, user }).whereNotNull('type');
        res.send(results);
      } else {
        // Only send an id->label map
        const results = await knex('imageclassifications').where({ datasetId, user }).whereNotNull('type').select('annotationId', 'type');
        res.send(mapValues(keyBy(results, 'annotationId'), 'type'));
      }
    } catch (err) {
      next(err);
    }
  });

  app.post('/manualsortapi', async (req, res, next) => {
    try {
      const { datasetId, user, annotationId, ...rest } = req.body;
      if ((await knex('imageclassifications').where({ datasetId, user, annotationId })).length > 0) {
        await knex('imageclassifications').where({ datasetId, user, annotationId }).update({ ...rest });
      } else {
        await knex('imageclassifications').insert({ datasetId, user, annotationId, ...rest });
      }
      res.send();
    } catch (err) {
      next(err);
    }
  });
};


module.exports = {
  configureImageClassifier
};
