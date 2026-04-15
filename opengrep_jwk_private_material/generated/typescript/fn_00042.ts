import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"p8qwjG0A1XdH","alg":"RS256","n":"VjVmYzyLylxCM4nC2cVuWyRV-aCRMOoZi6E_9OtWQMGPSWhP","e":"AQAB"}
const key42: any = {"kty":"RSA","kid":"p8qwjG0A1XdH","alg":"RS256","n":"VjVmYzyLylxCM4nC2cVuWyRV-aCRMOoZi6E_9OtWQMGPSWhP","e":"AQAB"};
void importJWK(key42, 'RS256');
