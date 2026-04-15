import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"EC","kid":"ORNyZLqsb_TJ","alg":"ES256","crv":"P-256","x":"a5DUOFx3emIqk3UZSBooFEctcPAOKZlYJARir2UTkeV","y":"QxK-jTqHV79Xx3y53FC1ye1mr6dpB1tkxYfuqRIej61","d":"oDC6bckp3hlBxQ18aSpdst9xgDI4qzc7GtyHgU1PtPtKTTJbm5DrrnLlx8MNgvsS"}
    String jwk = "{\"kty\":\"EC\",\"kid\":\"ORNyZLqsb_TJ\",\"alg\":\"ES256\",\"crv\":\"P-256\",\"x\":\"a5DUOFx3emIqk3UZSBooFEctcPAOKZlYJARir2UTkeV\",\"y\":\"QxK-jTqHV79Xx3y53FC1ye1mr6dpB1tkxYfuqRIej61\",\"d\":\"oDC6bckp3hlBxQ18aSpdst9xgDI4qzc7GtyHgU1PtPtKTTJbm5DrrnLlx8MNgvsS\"}";
    JWK.parse(jwk);
  }
}
