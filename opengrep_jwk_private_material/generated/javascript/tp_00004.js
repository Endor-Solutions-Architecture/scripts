import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"fboLhjtgR2ho","alg":"RS256","n":"IENpxJbL27gcuU7PM7BP6jORJF-kzMRIU6pNgDlQZQeISWbU","e":"AQAB","d":"bkIS85sn"}
const key4 = {"kty":"RSA","kid":"fboLhjtgR2ho","alg":"RS256","n":"IENpxJbL27gcuU7PM7BP6jORJF-kzMRIU6pNgDlQZQeISWbU","e":"AQAB","d":"bkIS85sn"};
void importJWK(key4, 'RS256');
