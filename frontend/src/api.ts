export type Me={actor:string;role:string;map_tile_key:string|null};
export type Area={id:number;name:string;authorization_ref:string;precision:string;run_count?:number;device_count?:number};
export type Run={id:number;collection_id:number;name:string;collector_coverage:number;completed:boolean};
export type Overview={areas:number;runs:number;observations:number;devices:number;unattributable:number;completed_runs:number};
export class ApiError extends Error { constructor(public status:number,message:string){super(message)}}
export async function api<T>(path:string, init:RequestInit={}):Promise<T>{const response=await fetch(path,{...init,credentials:"same-origin",headers:{"Content-Type":"application/json",...(init.headers||{})}});if(!response.ok)throw new ApiError(response.status,(await response.text()).replace(/^"|"$/g,""));return response.json() as Promise<T>}
export const send=<T=unknown>(path:string,data:unknown)=>api<T>(path,{method:"POST",body:JSON.stringify(data)});
