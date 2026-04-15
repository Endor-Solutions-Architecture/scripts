import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"dCWwueoy7NJz","alg":"RS256","n":"pd4fBpbwTVZZIAfrvTtF6YDBBwZSGBnvMGa4zxdtVXxXuELz","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"dCWwueoy7NJz\",\"alg\":\"RS256\",\"n\":\"pd4fBpbwTVZZIAfrvTtF6YDBBwZSGBnvMGa4zxdtVXxXuELz\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
