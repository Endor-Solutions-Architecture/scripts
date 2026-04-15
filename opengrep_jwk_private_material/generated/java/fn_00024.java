import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"DOvlcvm-kPMp","alg":"RS256","n":"IjrvqlZ6Nh4Hb4HgzKX7Gy1ACvArlwDFtWL84fCAjT5sMgfK","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"DOvlcvm-kPMp\",\"alg\":\"RS256\",\"n\":\"IjrvqlZ6Nh4Hb4HgzKX7Gy1ACvArlwDFtWL84fCAjT5sMgfK\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
