import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"Cg3SK7waCeXg","alg":"RS256","n":"f_vASUeGuYGkoDV5O6z1oAejZYvMDEZZu73DuDorOSzKgrAV","e":"AQAB","d":"2kks-ftcPicCDKyQrqmhsqNhOGkZFE_R8WlpKv1aMkwyLd6YtNhTtI160WG232by"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"Cg3SK7waCeXg\",\"alg\":\"RS256\",\"n\":\"f_vASUeGuYGkoDV5O6z1oAejZYvMDEZZu73DuDorOSzKgrAV\",\"e\":\"AQAB\",\"d\":\"2kks-ftcPicCDKyQrqmhsqNhOGkZFE_R8WlpKv1aMkwyLd6YtNhTtI160WG232by\"}";
    JWK.parse(jwk);
  }
}
