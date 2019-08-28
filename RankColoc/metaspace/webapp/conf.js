exports.PORT = "8080";

// The rest of the config isn't needed by RankColoc:
exports.AWS_ACCESS_KEY_ID = "";
exports.AWS_SECRET_ACCESS_KEY = "";
exports.AWS_REGION = "";

// either 's3' or the destination directory
// must match 'storage' value in src/clientConfig-coloc.js
exports.UPLOAD_DESTINATION = "";

exports.RAVEN_DSN = null;
