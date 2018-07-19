import gql from 'graphql-tag';

export interface MzImage {
  mz: number;
  url: string;
  totalIntensity: number;
  minIntensity: number;
  maxIntensity: number;
}

export const ICBlockAnnotationsQuery = gql`query AllAnnotations($filter: AnnotationFilter, $datasetFilter: DatasetFilter) {
    allAnnotations(filter: $filter, datasetFilter: $datasetFilter,
                   offset: 0, limit: 10000, orderBy: ORDER_BY_MZ, sortingOrder: ASCENDING) {
        id
        sumFormula
        adduct
        msmScore
        fdrLevel
        mz
        dataset {
          id
          name
        }
        isotopeImages {
          mz
          url
          minIntensity
          maxIntensity
          totalIntensity
        }
      }
  }`;

export interface ICBlockAnnotation {
  id: string;
  dataset: { id: string, name: string },
  sumFormula: string;
  adduct: string;
  msmScore: number;
  fdrLevel: number;
  mz: number;
  isotopeImages: MzImage[];
}

export interface AnnotationLabel {
  datasetId: string;
  user: string;
  annotationId: string;
  type: number;

  dsName?: string | null;
  sumFormula?: string | null;
  adduct?: string | null;
  msmScore?: number | null;
  fdrLevel?: number | null;
  mz?: number | null;
  ionImageUrl?: string | null;
  source?: string | null;
}
