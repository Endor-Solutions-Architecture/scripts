import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"T0RXTGcwW_oG","alg":"RS256","n":"_gi7Rb6BHlrZw4fLzOgvpHw5qIiqtthSBkp_3O-Qq71lxTbk","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"T0RXTGcwW_oG\",\"alg\":\"RS256\",\"n\":\"_gi7Rb6BHlrZw4fLzOgvpHw5qIiqtthSBkp_3O-Qq71lxTbk\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
