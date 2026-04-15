import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"UWF-VbCerywg","alg":"RS256","n":"ZQrNlK6AaBy7KPOaCU6KE2LQewo1cRJl-ppp4HXSFYOyLbjj","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"UWF-VbCerywg\",\"alg\":\"RS256\",\"n\":\"ZQrNlK6AaBy7KPOaCU6KE2LQewo1cRJl-ppp4HXSFYOyLbjj\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
