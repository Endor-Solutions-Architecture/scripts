import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"AAWoEJ_itXjw","alg":"RS256","n":"LKPMREUu_wyXbolKcaz94HPrOj-gx3yr1rXfeqsS1LNCP5tn","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"AAWoEJ_itXjw\",\"alg\":\"RS256\",\"n\":\"LKPMREUu_wyXbolKcaz94HPrOj-gx3yr1rXfeqsS1LNCP5tn\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
