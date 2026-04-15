import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"DPbQ6i_0C3Bz","alg":"RS256","n":"w4Mi6iFa7UTq5o7t_WEfjiVRVNhm1xNgnxIvxS0TeyG0NISf","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"DPbQ6i_0C3Bz\",\"alg\":\"RS256\",\"n\":\"w4Mi6iFa7UTq5o7t_WEfjiVRVNhm1xNgnxIvxS0TeyG0NISf\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
