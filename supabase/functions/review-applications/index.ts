import {makeHandler} from './handler.ts';
Deno.serve(makeHandler(key => Deno.env.get(key)));
