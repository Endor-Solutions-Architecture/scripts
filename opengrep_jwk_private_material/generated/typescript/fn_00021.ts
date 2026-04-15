import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"C_mXo5bWfbG1","alg":"RS256","n":"bIsawclE_9qYiIs2AtmOaLLUp2vtS13yfxydKpRoE4G465-m","e":"AQAB"}
const key21: any = {"kty":"RSA","kid":"C_mXo5bWfbG1","alg":"RS256","n":"bIsawclE_9qYiIs2AtmOaLLUp2vtS13yfxydKpRoE4G465-m","e":"AQAB"};
void importJWK(key21, 'RS256');
