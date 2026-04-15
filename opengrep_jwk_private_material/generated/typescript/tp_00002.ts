import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"k8QnhQjwucWY","alg":"HS256","k":"FhzwoEstrrAQVGNVPzu4dF1WJKpkUO2mGOrou0FHwwZltK8mFYkmOPxaS_pK0kzv"}
const key2: any = {"kty":"oct","kid":"k8QnhQjwucWY","alg":"HS256","k":"FhzwoEstrrAQVGNVPzu4dF1WJKpkUO2mGOrou0FHwwZltK8mFYkmOPxaS_pK0kzv"};
void importJWK(key2, 'HS256');
