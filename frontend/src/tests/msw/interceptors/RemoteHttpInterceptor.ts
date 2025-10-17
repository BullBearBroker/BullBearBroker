import { loadInterceptor } from "./resolve";
const interceptor = loadInterceptor("RemoteHttpInterceptor");
// # QA fix: conversión a export default para compatibilidad con Babel/ESM
export default interceptor;
