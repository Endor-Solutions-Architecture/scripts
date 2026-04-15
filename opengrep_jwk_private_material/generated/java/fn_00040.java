import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"aV8sdG6vmYVI","alg":"RS256","n":"UKQ5ZCpOkl0wscbtaSOqqegv_6-xuFm02oChy2i-c-DFWB8k","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"aV8sdG6vmYVI\",\"alg\":\"RS256\",\"n\":\"UKQ5ZCpOkl0wscbtaSOqqegv_6-xuFm02oChy2i-c-DFWB8k\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
