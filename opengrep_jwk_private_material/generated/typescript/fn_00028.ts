import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"V_OP4Llsnr9u","alg":"RS256","n":"yxOZ9FWdxeH7rw9ynfw_o71GOEBkOHCalzseWYyoWAsCO9O3","e":"AQAB"}
const key28: any = {"kty":"RSA","kid":"V_OP4Llsnr9u","alg":"RS256","n":"yxOZ9FWdxeH7rw9ynfw_o71GOEBkOHCalzseWYyoWAsCO9O3","e":"AQAB"};
void importJWK(key28, 'RS256');
