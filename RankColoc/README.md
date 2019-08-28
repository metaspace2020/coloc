# RankColoc

RankColoc was rapidly prototyped using the [METASPACE codebase](https://github.com/metaspace2020/metaspace/) as a foundation,
allowing its back-end, image display and ranking to be reused. This directory contains a stripped-down fork of METASPACE
including only the components necessary to run RankColoc. The RankColoc-specific changes can be found 
[in this commit range](https://github.com/metaspace2020/coloc/compare/2d316a9049c561e5f5b7a0deded05930a435dc14...67f8fa10e5aa1f7a1052c4adaae997a489b9ce52).

## Installation

* Clone the repository
* Enter the `RankColoc/webapp` with a command prompt
* Run `yarn install`
* Customize `conf.js` to change the port if needed
* Customize `src/clientConfig-coloc.json` to change the external host name & port for the local server if needed
* Run `yarn run build && yarn run start`
* The server should now be running at http://localhost:8080/manualsort?user=demo&pix=0.2&fdrLevel=0.1&sets=2016-09-21_16h06m53s:10-15 

## Acknowledgements

<img src="https://user-images.githubusercontent.com/26366936/42041116-818a0048-7af1-11e8-82d7-15c9d7ab0441.png" width="98" height="65"><img src="https://user-images.githubusercontent.com/26366936/42041125-845b691a-7af1-11e8-9c43-bfbf2152d6e4.png" width="102" height="65">

The METASPACE project, on which RankColoc is based, is funded from the 
[European Horizon2020](https://ec.europa.eu/programmes/horizon2020/)
project [METASPACE](http://project.metaspace2020.eu/) (no. 634402),
[NIH NIDDK project KPMP](http://kpmp.org/)
and internal funds of the [European Molecular Biology Laboratory](https://www.embl.org/).

## License

Unless specified otherwise in file headers or LICENSE files present in subdirectories,
all files are licensed under the [Apache 2.0 license](LICENSE).
