# Measuring co-localization of ion images

This repository is devoted to a computational project on measuring co-localization of images in imaging mass spectrometry data. The project is carried out by the [Alexandrov team](https://www.embl.de/research/units/scb/alexandrov/) at EMBL Heidelberg. We used public data from [METASPACE](http://metaspace2020.eu) to create a gold standard set of ranked ion image pairs, as well as developed and evaluated several measures of co-localization of ion images.

Team:

- [Katja Ovchinnikova](http://ovchinnikova.me/): pixel-based co-localization method development, gold standard preparation
- Alexander Rakhlin: deep learning based co-localization method development
- [Lachlan Stuart](https://github.com/LachlanStuart): development of the RankColoc web app
- [Theodore Alexandrov](https://www.embl.de/research/units/scb/alexandrov/members/index.php?s_personId=CP-60020464): supervision, gold standard preparation

## Creating gold standard ion images

### Using public METASPACE datasets

We used public datasets from [METASPACE](http://metaspace2020.eu), a community-populated knowledge base of metabolite images. Please see the section Acknowledgements acknowledging contributors of the used data.

RankColoc was rapidly prototyped using the [METASPACE codebase](https://github.com/metaspace2020/metaspace/) as a foundation,
allowing its back-end, image display and ranking to be reused.
The RankColoc-specific changes can be found [in this commit range](???).

It can be run by [starting the METASPACE webapp](???).

## Data

### Gold standard

The gold standard is available [in this commit range](https://github.com/metaspace2020/offsample/coloc/GS).
The ion images are available under `gs_imgs1` and `gs_imgs2` file names. To join both files into one arhive run `cat gs_imgs* > gs_imgs.tar.gz`

The initial expert rankings can be found in `rankings.csv`, the filtered gold standard with average rankings is in `coloc_gs.csv`.

## Future steps

We are planning to integrate the best methods into [https://metaspace2020.eu](https://metaspace2020.eu).

## License

Unless specified otherwise in file headers or LICENSE files present in subdirectories, all files in this repository are licensed under the [Apache 2.0 license](LICENSE).
