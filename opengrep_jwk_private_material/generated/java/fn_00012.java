import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"gu3iHL6H2Iyk","alg":"RS256","n":"wlNa5bCkpriXebt9vWcReNd0d4uYqH35bsrMZZPK3sMwPXfm","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"gu3iHL6H2Iyk\",\"alg\":\"RS256\",\"n\":\"wlNa5bCkpriXebt9vWcReNd0d4uYqH35bsrMZZPK3sMwPXfm\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
