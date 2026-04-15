import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"qOq1Rx7MCWPF","alg":"RS256","n":"wavkk0-NDSpN1L_vMQPCWzKRO-aIITMyugC6HwWMOfE7b4em","e":"AQAB","d":"zco8X15-"}
const key9: any = {"kty":"RSA","kid":"qOq1Rx7MCWPF","alg":"RS256","n":"wavkk0-NDSpN1L_vMQPCWzKRO-aIITMyugC6HwWMOfE7b4em","e":"AQAB","d":"zco8X15-"};
void importJWK(key9, 'RS256');
