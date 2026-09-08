export type Me={actor:string;role:string};
export type Area={id:number;name:string;authorization_ref:string;precision:string};
export type Run={id:number;survey_area_id:number;name:string;collector_coverage:number;completed:boolean};
export type Overview={areas:number;runs:number;observations:number;devices:number};
export class ApiError extends Error { constructor(public status:number,message:string){super(message)}}
export async function api<T>(path:string, init:RequestInit={}):Promise<T>{const response=await fetch(path,{...init,credentials:"same-origin",headers:{"Content-Type":"application/json",...(init.headers||{})}});if(!response.ok)throw new ApiError(response.status,(await response.text()).replace(/^"|"$/g,""));return response.json() as Promise<T>}
export const send=(path:string,data:unknown)=>api(path,{method:"POST",body:JSON.stringify(data)});
