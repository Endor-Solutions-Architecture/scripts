import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"-9IGRRBOVy3a","alg":"RS256","n":"Mc82w9A5ruK5wb_iMiEiuPp5g2NQV-fK_K92eXwP9WtjF-Ir","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"-9IGRRBOVy3a\",\"alg\":\"RS256\",\"n\":\"Mc82w9A5ruK5wb_iMiEiuPp5g2NQV-fK_K92eXwP9WtjF-Ir\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
