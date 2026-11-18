import {retirementsApi} from '../api/retirements.js';
export const retirementsStore={items:[],async refresh(){this.items=await retirementsApi.list();return this.items;}};
