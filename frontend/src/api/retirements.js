import {api} from './client.js';
export const retirementsApi={list:()=>api('/retirements'),create:(relationId,data)=>api('/relations/'+relationId+'/retirements','POST',data),precheck:id=>api('/retirements/'+id+'/precheck','POST'),confirm:id=>api('/retirements/'+id+'/confirm','POST')};
