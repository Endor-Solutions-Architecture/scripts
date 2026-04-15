import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"DORRCtj-Dr94","alg":"RS256","n":"AeLyfcmrAF-FYYgX3DkHFBz9Mv_sGnb7itoo_lw4vlggWDee","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"DORRCtj-Dr94\",\"alg\":\"RS256\",\"n\":\"AeLyfcmrAF-FYYgX3DkHFBz9Mv_sGnb7itoo_lw4vlggWDee\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
