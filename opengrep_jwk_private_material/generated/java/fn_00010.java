import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"kkjXsUBasnsT","alg":"RS256","n":"5j4PhSoh-Wz8cKQDNCay_dG5nCTQCDeapv-Vh58nuzvzyzRD","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"kkjXsUBasnsT\",\"alg\":\"RS256\",\"n\":\"5j4PhSoh-Wz8cKQDNCay_dG5nCTQCDeapv-Vh58nuzvzyzRD\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
