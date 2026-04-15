import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"_d7nLh3eL9ec","alg":"RS256","n":"iQgt9SKNoccN3qqc4C9d7vYDemMwX2pHnzJxmjyHpoJ809kU","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"_d7nLh3eL9ec\",\"alg\":\"RS256\",\"n\":\"iQgt9SKNoccN3qqc4C9d7vYDemMwX2pHnzJxmjyHpoJ809kU\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
