import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"Ual7M-qzzm_g","alg":"RS256","n":"ef7gZ81_Ot-3R1DIa2GwQWthWn3r3CmxlUR-JbwlqzTdAmfu","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"Ual7M-qzzm_g\",\"alg\":\"RS256\",\"n\":\"ef7gZ81_Ot-3R1DIa2GwQWthWn3r3CmxlUR-JbwlqzTdAmfu\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
