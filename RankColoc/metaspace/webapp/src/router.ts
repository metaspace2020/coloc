import Vue from 'vue';
import VueRouter from 'vue-router';
import AboutPage from './modules/App/AboutPage.vue';
import DatasetsPage from './modules/Datasets/DatasetsPage.vue';
import {DialogPage, ResetPasswordPage} from './modules/Account';

Vue.use(VueRouter);

const asyncPages = {
  AnnotationsPage: () => import(/* webpackPrefetch: true, webpackChunkName: "AnnotationsPage" */ './modules/Annotations/AnnotationsPage.vue'),
  DatasetSummary: () => import(/* webpackPrefetch: true, webpackChunkName: "DatasetSummary" */ './modules/Datasets/summary/DatasetSummary.vue'),
  MetadataEditPage: () => import(/* webpackPrefetch: true, webpackChunkName: "MetadataEditPage" */ './modules/MetadataEditor/MetadataEditPage.vue'),
  ImageAlignmentPage: () => import(/* webpackPrefetch: true, webpackChunkName: "ImageAlignmentPage" */ './modules/ImageAlignment/ImageAlignmentPage.vue'),
  UploadPage: () => import(/* webpackPrefetch: true, webpackChunkName: "UploadPage" */ './modules/MetadataEditor/UploadPage.vue'),

  // These pages are relatively small as they don't have any big 3rd party dependencies, so pack them together
  DatasetTable: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/Datasets/list/DatasetTable.vue'),
  HelpPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/App/HelpPage.vue'),
  EditUserPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/UserProfile/EditUserPage.vue'),
  CreateGroupPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/GroupProfile/CreateGroupPage.vue'),
  ViewGroupPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/GroupProfile/ViewGroupPage.vue'),
  ViewProjectPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/Project/ViewProjectPage.vue'),
  ProjectsListPage: () => import(/* webpackPrefetch: true, webpackChunkName: "Bundle1" */ './modules/Project/ProjectsListPage.vue'),
};

const convertLegacyHashUrls = () => {
  const {pathname, hash} = window.location;
  if (pathname === '/' && hash && hash.startsWith('#/')) {
    history.replaceState(undefined, undefined, hash.slice(1));
  }
};
convertLegacyHashUrls();

const router = new VueRouter({
  mode: 'history',
  routes: [
    { path: '/', redirect: '/manualsort' },
    { path: '/about', component: AboutPage },
    { path: '/annotations', component: asyncPages.AnnotationsPage },
    {
      path: '/datasets',
      component: DatasetsPage,
      children: [
        {path: '', component: asyncPages.DatasetTable},
        {path: 'summary', component: asyncPages.DatasetSummary},
      ]
    },
    { path: '/datasets/edit/:dataset_id', name: 'edit-metadata', component: asyncPages.MetadataEditPage },
    { path: '/datasets/:dataset_id/add-optical-image', name: 'add-optical-image', component: asyncPages.ImageAlignmentPage },
    { path: '/upload', component: asyncPages.UploadPage },
    { path: '/help', component: asyncPages.HelpPage },
    { path: '/user/me', component: asyncPages.EditUserPage },

    { path: '/admin/health', component: async () => await import('./modules/Admin/SystemHealthPage.vue') },
    { path: '/admin/groups', component: async () => await import('./modules/Admin/GroupsListPage.vue') },

    { path: '/account/sign-in', component: DialogPage, props: {dialog: 'signIn'} },
    { path: '/account/create-account', component: DialogPage, props: {dialog: 'createAccount'} },
    { path: '/account/forgot-password', component: DialogPage, props: {dialog: 'forgotPassword'} },
    { path: '/account/reset-password', component: ResetPasswordPage },

    { path: '/group/create', component: asyncPages.CreateGroupPage },
    { path: '/group/:groupIdOrSlug', name: 'group', component: asyncPages.ViewGroupPage },
    { path: '/project/:projectIdOrSlug', name: 'project', component: asyncPages.ViewProjectPage },
    { path: '/projects', component: asyncPages.ProjectsListPage },
    { path: '/manualsort', component: async () => (await import(/* webpackPrefetch: true, webpackChunkName: "ImageClassifierPage" */ './modules/ImageClassifier')).ImageClassifierPage  },
  ],
  parseQuery: query => {
    var res: Record<string, string> = {};

    query = query.trim().replace(/^(\?|#|&)/, '');

    if (!query) {
      return res
    }

    query.split('&').forEach(function (param) {
      var parts = param.split('=');
      var key = decodeURIComponent(parts.shift()!);
      var val = parts.length > 0
        ? decodeURIComponent(parts.join('='))
        : null;

      if (res[key] === undefined) {
        res[key] = val!;
      } else if (Array.isArray(res[key])) {
        (res[key] as any).push(val);
      } else {
        (res[key] as any) = [res[key], val];
      }
    });

    return res
  },
  stringifyQuery: (obj: object) => {
    var res = obj ? Object.keys(obj).map(function (key) {
      var val = (obj as Record<string,string>)[key];

      if (val === undefined) {
        return ''
      }

      if (val === null) {
        return encode(key)
      }

      if (Array.isArray(val)) {
        var result: string[] = [];
        val.forEach(function (val2) {
          if (val2 === undefined) {
            return
          }
          if (val2 === null) {
            result.push(encode(key));
          } else {
            result.push(encode(key) + '=' + encode(val2));
          }
        });
        return result.join('&')
      }

      return encode(key) + '=' + encode(val)
    }).filter(function (x) { return x.length > 0; }).join('&') : null;
    return res ? ("?" + res) : ''
  },

});

function encode(str: string) {
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

export default router;
