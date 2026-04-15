import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"qAEFPhAdT6eQ","alg":"RS256","n":"-_1nI4Ds0B29jU424-dte9Hpw6u7jPeV2sr0yMYxbTFhItUr","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"qAEFPhAdT6eQ\",\"alg\":\"RS256\",\"n\":\"-_1nI4Ds0B29jU424-dte9Hpw6u7jPeV2sr0yMYxbTFhItUr\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
