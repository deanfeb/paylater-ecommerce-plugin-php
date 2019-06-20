const nunjucks = require("nunjucks");
const yaml = require("js-yaml");
const fs = require("fs");

function generateNginxConfig() {
    const result = nunjucks.render("magento2.conf.njk", {
        build_directory: __dirname + "/upload/"
    });
    const outputFd = fs.openSync("/etc/nginx/conf.d/magento2.conf", "w");
    fs.writeSync(outputFd, result);
}

generateNginxConfig();
