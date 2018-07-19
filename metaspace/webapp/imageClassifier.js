const {mapValues, keyBy} = require('lodash');

const configureKnex = async () => {
  const knex = require('knex')({
    client: 'sqlite3',
    connection: {
      filename: './imageclassification.sqlite',
    },
    useNullAsDefault: true,
  });

  if (!await knex.schema.hasTable('imageclassifications')) {
    await knex.schema.createTable('imageclassifications', (table) => {
      table.increments();
      // Important fields
      table.string('datasetId');
      table.string('user');
      table.string('annotationId');
      table.int('type');
      table.unique(['datasetId','user','annotationId']);
      // Additional info
      table.string('dsName');
      table.string('sumFormula');
      table.string('adduct');
      table.float('msmScore');
      table.float('fdrLevel');
      table.float('mz');
      table.string('ionImageUrl');
      table.string('source');
    });
  }

  return knex;
};

const configureImageClassifier = async (app) => {
  const knex = await configureKnex();

  app.get('/imageclassifier', async (req, res, next) => {
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

  app.post('/imageclassifier', async (req, res, next) => {
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
