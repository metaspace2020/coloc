import * as _ from 'lodash';
const csvStringifySync = require('csv-stringify/lib/sync');
import writeFileAtomic from 'write-file-atomic';
import * as path from 'path';



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
      table.string('baseAnnotationId');
      table.string('otherAnnotationId');
      table.integer('order');
      // Additional info
      table.string('dsName');
      table.float('intThreshold');
      table.string('baseSf');
      table.string('baseAdduct');
      table.float('baseAvgInt');
      table.string('baseIonImageUrl');
      table.string('otherSf');
      table.string('otherAdduct');
      table.string('otherIonImageUrl');
      table.float('otherAvgInt');
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

  return knex;
};

const configureImageClassifier = async (app) => {
  const knex = await configureKnex();


  app.get('/manualsortapi/export', async (req, res, next) => {
    try {
      console.log('exporting');

      let rows = await knex('manualsort')
        .whereNull('deleted_at')
        .orderBy(['datasetId', 'user', 'baseAnnotationId', 'order']);
      var host = 'http://' + req.headers.host;

      rows = rows.map(r => {
        return {
          ..._.omit(r, ['deleted_at']),
          link: `${host}/manualsort?ds=${r.datasetId}&user=${r.user}&intthreshold=${r.intThreshold}&sets=${r.setIdx}`,
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
                                              .orderBy(['baseAnnotationId', 'order']);
      const groupedResults = Object.values(_.groupBy(results, 'baseAnnotationId'));
      const structuredResults = groupedResults.map(grp => {
        return {
          ..._.pickBy(grp[0], (v, k) => !k.startsWith('other') && !['order','id','created_at','deleted_at'].includes(k)),
          otherAnnotations: grp.map(item => {
            return _.pickBy(item, (v, k) => k.startsWith('other'))
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
            .map((ann, order) => ({ ...ann, ...baseAnn, baseAnnotationId, datasetId, user, order })));
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
