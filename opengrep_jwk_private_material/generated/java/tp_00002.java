import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"oct","kid":"zzVQelPYlapP","alg":"HS256","k":"aEefNXnlJ16c9kyJ9u_zuHqYhq2qAdtaFIPSIqhLTjKZldi28YJWKSzGF51cPX5U"}
    String jwk = "{\"kty\":\"oct\",\"kid\":\"zzVQelPYlapP\",\"alg\":\"HS256\",\"k\":\"aEefNXnlJ16c9kyJ9u_zuHqYhq2qAdtaFIPSIqhLTjKZldi28YJWKSzGF51cPX5U\"}";
    JWK.parse(jwk);
  }
}
